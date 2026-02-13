import asyncio
import json
import logging
import uuid
from typing import Optional

import aiohttp
import websockets
from pydantic import BaseModel


logger = logging.getLogger(__name__)

# Marker used to delimit file data in stdout from the file-collection cell.
_FILES_MARKER_START = "__OWUI_FILES_START__"
_FILES_MARKER_END = "__OWUI_FILES_END__"

# Maximum individual file size (in bytes) we will pull back from the kernel.
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class FileResult(BaseModel):
    """Represents a file created during code execution."""

    name: str
    data: str  # base64-encoded file content
    size: int


class ResultModel(BaseModel):
    """
    Execute Code Result Model
    """

    stdout: Optional[str] = ""
    stderr: Optional[str] = ""
    result: Optional[str] = ""
    files: Optional[list[FileResult]] = None


class JupyterCodeExecuter:
    """
    Execute code in jupyter notebook
    """

    def __init__(
        self,
        base_url: str,
        code: str,
        token: str = "",
        password: str = "",
        timeout: int = 60,
    ):
        """
        :param base_url: Jupyter server URL (e.g., "http://localhost:8888")
        :param code: Code to execute
        :param token: Jupyter authentication token (optional)
        :param password: Jupyter password (optional)
        :param timeout: WebSocket timeout in seconds (default: 60s)
        """
        self.base_url = base_url
        self.code = code
        self.token = token
        self.password = password
        self.timeout = timeout
        self.kernel_id = ""
        if self.base_url[-1] != "/":
            self.base_url += "/"
        self.session = aiohttp.ClientSession(trust_env=True, base_url=self.base_url)
        self.params = {}
        self.result = ResultModel()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.kernel_id:
            try:
                async with self.session.delete(
                    f"api/kernels/{self.kernel_id}", params=self.params
                ) as response:
                    response.raise_for_status()
            except Exception as err:
                logger.exception("close kernel failed, %s", err)
        await self.session.close()

    async def run(self) -> ResultModel:
        try:
            await self.sign_in()
            await self.init_kernel()
            await self.execute_code()
        except Exception as err:
            logger.exception("execute code failed, %s", err)
            self.result.stderr = f"Error: {err}"
        return self.result

    async def sign_in(self) -> None:
        # password authentication
        if self.password and not self.token:
            async with self.session.get("login") as response:
                response.raise_for_status()
                xsrf_token = response.cookies["_xsrf"].value
                if not xsrf_token:
                    raise ValueError("_xsrf token not found")
                self.session.cookie_jar.update_cookies(response.cookies)
                self.session.headers.update({"X-XSRFToken": xsrf_token})
            async with self.session.post(
                "login",
                data={"_xsrf": xsrf_token, "password": self.password},
                allow_redirects=False,
            ) as response:
                response.raise_for_status()
                self.session.cookie_jar.update_cookies(response.cookies)

        # token authentication
        if self.token:
            self.params.update({"token": self.token})

    async def init_kernel(self) -> None:
        async with self.session.post(url="api/kernels", params=self.params) as response:
            response.raise_for_status()
            kernel_data = await response.json()
            self.kernel_id = kernel_data["id"]

    def init_ws(self) -> tuple:
        ws_base = self.base_url.replace("http", "ws", 1)
        ws_params = "?" + "&".join([f"{key}={val}" for key, val in self.params.items()])
        websocket_url = f"{ws_base}api/kernels/{self.kernel_id}/channels{ws_params if len(ws_params) > 1 else ''}"
        ws_headers = {}
        if self.password and not self.token:
            ws_headers = {
                "Cookie": "; ".join(
                    [
                        f"{cookie.key}={cookie.value}"
                        for cookie in self.session.cookie_jar
                    ]
                ),
                **self.session.headers,
            }
        return websocket_url, ws_headers

    async def execute_code(self) -> None:
        # initialize ws
        websocket_url, ws_headers = self.init_ws()
        # execute
        async with websockets.connect(
            websocket_url, additional_headers=ws_headers
        ) as ws:
            await self.execute_in_jupyter(ws)

    # ------------------------------------------------------------------
    # Low-level helper: execute a single code cell and collect output.
    # ------------------------------------------------------------------

    async def _execute_cell(self, ws, code: str) -> tuple:
        """Execute a single code cell and return (stdout, stderr, result_list)."""
        msg_id = uuid.uuid4().hex
        await ws.send(
            json.dumps(
                {
                    "header": {
                        "msg_id": msg_id,
                        "msg_type": "execute_request",
                        "username": "user",
                        "session": uuid.uuid4().hex,
                        "date": "",
                        "version": "5.3",
                    },
                    "parent_header": {},
                    "metadata": {},
                    "content": {
                        "code": code,
                        "silent": False,
                        "store_history": True,
                        "user_expressions": {},
                        "allow_stdin": False,
                        "stop_on_error": True,
                    },
                    "channel": "shell",
                }
            )
        )
        stdout, stderr, result = "", "", []
        while True:
            try:
                message = await asyncio.wait_for(ws.recv(), self.timeout)
                message_data = json.loads(message)
                if message_data.get("parent_header", {}).get("msg_id") != msg_id:
                    continue
                msg_type = message_data.get("msg_type")
                match msg_type:
                    case "stream":
                        if message_data["content"]["name"] == "stdout":
                            stdout += message_data["content"]["text"]
                        elif message_data["content"]["name"] == "stderr":
                            stderr += message_data["content"]["text"]
                    case "execute_result" | "display_data":
                        data = message_data["content"]["data"]
                        if "image/png" in data:
                            result.append(f"data:image/png;base64,{data['image/png']}")
                        elif "text/plain" in data:
                            result.append(data["text/plain"])
                    case "error":
                        stderr += "\n".join(message_data["content"]["traceback"])
                    case "status":
                        if message_data["content"]["execution_state"] == "idle":
                            break
            except asyncio.TimeoutError:
                stderr += "\nExecution timed out."
                break
        return stdout.strip(), stderr.strip(), result

    # ------------------------------------------------------------------
    # High-level orchestrator
    # ------------------------------------------------------------------

    async def execute_in_jupyter(self, ws) -> None:
        # Step 1: Setup – create /mnt/data/ and snapshot existing files.
        setup_code = (
            "import os as _os\n"
            "_os.makedirs('/mnt/data', exist_ok=True)\n"
            "_owui_pre_files = set(_os.listdir('/mnt/data'))\n"
        )
        await self._execute_cell(ws, setup_code)

        # Step 2: Execute the user's code.
        stdout, stderr, result = await self._execute_cell(ws, self.code)

        self.result.stdout = stdout
        self.result.stderr = stderr
        self.result.result = "\n".join(result).strip() if result else ""

        # Step 3: Collect any new files created under /mnt/data/.
        collect_code = (
            "import os as _os, json as _json, base64 as _b64\n"
            "try:\n"
            "    _owui_post_files = set(_os.listdir('/mnt/data'))\n"
            "    _owui_new = []\n"
            "    for _f in sorted(_owui_post_files - _owui_pre_files):\n"
            "        _fp = _os.path.join('/mnt/data', _f)\n"
            f"        if _os.path.isfile(_fp) and _os.path.getsize(_fp) < {_MAX_FILE_SIZE}:\n"
            "            with open(_fp, 'rb') as _fh:\n"
            "                _owui_new.append({'name': _f, 'data': _b64.b64encode(_fh.read()).decode(), 'size': _os.path.getsize(_fp)})\n"
            "    if _owui_new:\n"
            f"        print('{_FILES_MARKER_START}' + _json.dumps(_owui_new) + '{_FILES_MARKER_END}')\n"
            "except Exception:\n"
            "    pass\n"
        )
        file_stdout, _, _ = await self._execute_cell(ws, collect_code)

        # Parse file data from the collection cell output.
        files = self._parse_file_output(file_stdout)
        if files:
            self.result.files = files
            logger.info(
                "Collected %d file(s) from code execution: %s",
                len(files),
                [f.name for f in files],
            )

    # ------------------------------------------------------------------
    # Parse the special file-output marker from stdout.
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_file_output(stdout: str) -> list[FileResult] | None:
        if _FILES_MARKER_START not in stdout:
            return None
        try:
            start = stdout.index(_FILES_MARKER_START) + len(_FILES_MARKER_START)
            end = stdout.index(_FILES_MARKER_END, start)
            payload = stdout[start:end]
            raw_files = json.loads(payload)
            return [FileResult(**f) for f in raw_files]
        except Exception as exc:
            logger.warning("Failed to parse file output: %s", exc)
            return None


async def execute_code_jupyter(
    base_url: str, code: str, token: str = "", password: str = "", timeout: int = 60
) -> dict:
    async with JupyterCodeExecuter(
        base_url, code, token, password, timeout
    ) as executor:
        result = await executor.run()
        return result.model_dump()
