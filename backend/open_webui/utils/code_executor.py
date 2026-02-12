import logging
import docker
from pathlib import Path
from typing import Optional, Dict, Any

from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


class DockerCodeExecutor:
    """
    Manages Docker container execution for Python code.
    Each execution runs in a fresh container with isolated workspace.
    """

    def __init__(self, docker_socket: str = "unix:///var/run/docker.sock"):
        """
        Initialize Docker client.
        
        Args:
            docker_socket: Path to Docker socket (default: unix:///var/run/docker.sock)
        """
        try:
            self.client = docker.DockerClient(base_url=docker_socket)
            # Test connection
            self.client.ping()
            log.info("Docker client initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize Docker client: {e}")
            raise

    def execute_python_code(
        self,
        code: str,
        workspace_path: Path,
        timeout: int = 30,
        image: str = "python:3.11-slim"
    ) -> Dict[str, Any]:
        """
        Execute Python code in a fresh Docker container.
        
        Args:
            code: Python code to execute
            workspace_path: Path to workspace directory on host
            timeout: Execution timeout in seconds (default: 30)
            image: Docker image to use (default: python:3.11-slim)
            
        Returns:
            Dict with keys:
                - success: bool
                - output: str (stdout)
                - error: str (stderr)
                - exit_code: int
        """
        try:
            # Ensure workspace exists
            workspace_path.mkdir(parents=True, exist_ok=True)

            # Create a container with the workspace mounted
            container = self.client.containers.run(
                image=image,
                command=["python", "-c", code],
                volumes={
                    str(workspace_path): {
                        "bind": "/workspace",
                        "mode": "rw"
                    }
                },
                working_dir="/workspace",
                network_mode="none",  # Disable network access for security
                mem_limit="512m",  # Limit memory
                cpu_quota=50000,  # Limit CPU (50% of one core)
                detach=True,
                remove=False,  # We'll remove it manually after getting logs
            )

            # Wait for container to complete with timeout
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)

            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")

            # Split stdout and stderr if possible
            # Docker combines them, so we'll return combined output
            output = logs
            error = "" if exit_code == 0 else logs

            # Clean up container
            container.remove(force=True)

            return {
                "success": exit_code == 0,
                "output": output,
                "error": error,
                "exit_code": exit_code
            }

        except docker.errors.ContainerError as e:
            log.error(f"Container error: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Container error: {str(e)}",
                "exit_code": e.exit_status if hasattr(e, 'exit_status') else -1
            }
        except docker.errors.ImageNotFound as e:
            log.error(f"Image not found: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Docker image '{image}' not found",
                "exit_code": -1
            }
        except docker.errors.APIError as e:
            log.error(f"Docker API error: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Docker API error: {str(e)}",
                "exit_code": -1
            }
        except Exception as e:
            log.error(f"Unexpected error during code execution: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Execution error: {str(e)}",
                "exit_code": -1
            }

    def pull_image(self, image: str = "python:3.11-slim") -> bool:
        """
        Pull Docker image if not already available.
        
        Args:
            image: Docker image to pull
            
        Returns:
            True if successful, False otherwise
        """
        try:
            log.info(f"Pulling Docker image: {image}")
            self.client.images.pull(image)
            log.info(f"Successfully pulled image: {image}")
            return True
        except Exception as e:
            log.error(f"Failed to pull image {image}: {e}")
            return False

    def check_image_exists(self, image: str = "python:3.11-slim") -> bool:
        """
        Check if Docker image exists locally.
        
        Args:
            image: Docker image to check
            
        Returns:
            True if image exists, False otherwise
        """
        try:
            self.client.images.get(image)
            return True
        except docker.errors.ImageNotFound:
            return False
        except Exception as e:
            log.error(f"Error checking image {image}: {e}")
            return False

    def close(self):
        """Close Docker client connection."""
        try:
            self.client.close()
        except Exception as e:
            log.error(f"Error closing Docker client: {e}")
