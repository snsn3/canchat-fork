import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user


class TestCode(AbstractPostgresTest):
    BASE_PATH = "/api/v1/code"

    def setup_class(cls):
        super().setup_class()

    def setup_method(self):
        super().setup_method()
        from open_webui.models.code_sessions import CodeSessions

        self.code_sessions = CodeSessions()

    def teardown_method(self):
        super().teardown_method()
        # Clean up any test workspaces
        from open_webui.env import DATA_DIR
        workspace_dir = Path(DATA_DIR) / "workspaces"
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)

    def test_create_code_session(self):
        """Test creating a new code session"""
        with mock_webui_user(id="test_user_1"):
            response = self.fast_api_client.post(self.create_url("/sessions"))
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["user_id"] == "test_user_1"
        assert data["workspace_path"] is not None
        assert "workspaces/test_user_1" in data["workspace_path"]
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_get_code_session(self):
        """Test getting a code session by ID"""
        # Create a session first
        with mock_webui_user(id="test_user_1"):
            create_response = self.fast_api_client.post(self.create_url("/sessions"))
            session_id = create_response.json()["id"]
            
            # Get the session
            get_response = self.fast_api_client.get(
                self.create_url(f"/sessions/{session_id}")
            )
        
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == session_id
        assert data["user_id"] == "test_user_1"

    def test_get_code_session_not_found(self):
        """Test getting a non-existent code session"""
        with mock_webui_user(id="test_user_1"):
            response = self.fast_api_client.get(
                self.create_url("/sessions/nonexistent_id")
            )
        
        assert response.status_code == 404

    def test_get_code_session_forbidden(self):
        """Test getting a code session that belongs to another user"""
        # Create a session as user 1
        with mock_webui_user(id="test_user_1"):
            create_response = self.fast_api_client.post(self.create_url("/sessions"))
            session_id = create_response.json()["id"]
        
        # Try to get it as user 2
        with mock_webui_user(id="test_user_2"):
            response = self.fast_api_client.get(
                self.create_url(f"/sessions/{session_id}")
            )
        
        assert response.status_code == 403

    def test_list_code_sessions(self):
        """Test listing code sessions for a user"""
        with mock_webui_user(id="test_user_1"):
            # Create two sessions
            self.fast_api_client.post(self.create_url("/sessions"))
            self.fast_api_client.post(self.create_url("/sessions"))
            
            # List sessions
            response = self.fast_api_client.get(self.create_url("/sessions"))
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(session["user_id"] == "test_user_1" for session in data)

    def test_delete_code_session(self):
        """Test deleting a code session"""
        with mock_webui_user(id="test_user_1"):
            # Create a session
            create_response = self.fast_api_client.post(self.create_url("/sessions"))
            session_id = create_response.json()["id"]
            
            # Delete the session
            delete_response = self.fast_api_client.delete(
                self.create_url(f"/sessions/{session_id}")
            )
        
        assert delete_response.status_code == 200
        assert delete_response.json()["success"] is True

    def test_delete_code_session_not_found(self):
        """Test deleting a non-existent code session"""
        with mock_webui_user(id="test_user_1"):
            response = self.fast_api_client.delete(
                self.create_url("/sessions/nonexistent_id")
            )
        
        assert response.status_code == 404

    def test_delete_code_session_forbidden(self):
        """Test deleting a code session that belongs to another user"""
        # Create a session as user 1
        with mock_webui_user(id="test_user_1"):
            create_response = self.fast_api_client.post(self.create_url("/sessions"))
            session_id = create_response.json()["id"]
        
        # Try to delete it as user 2
        with mock_webui_user(id="test_user_2"):
            response = self.fast_api_client.delete(
                self.create_url(f"/sessions/{session_id}")
            )
        
        assert response.status_code == 403

    @patch("open_webui.routers.code.DockerCodeExecutor")
    def test_execute_code_success(self, mock_executor_class):
        """Test successful code execution"""
        # Mock the Docker executor
        mock_executor = MagicMock()
        mock_executor.check_image_exists.return_value = True
        mock_executor.execute_python_code.return_value = {
            "success": True,
            "output": "Hello, World!\n",
            "error": "",
            "exit_code": 0
        }
        mock_executor_class.return_value = mock_executor

        with mock_webui_user(id="test_user_1"):
            # Create a session
            create_response = self.fast_api_client.post(self.create_url("/sessions"))
            session_id = create_response.json()["id"]
            
            # Execute code
            execute_response = self.fast_api_client.post(
                self.create_url(f"/sessions/{session_id}/execute"),
                json={"code": "print('Hello, World!')"}
            )
        
        assert execute_response.status_code == 200
        data = execute_response.json()
        assert data["success"] is True
        assert data["output"] == "Hello, World!\n"
        assert data["exit_code"] == 0

    @patch("open_webui.routers.code.DockerCodeExecutor")
    def test_execute_code_with_error(self, mock_executor_class):
        """Test code execution with error"""
        # Mock the Docker executor
        mock_executor = MagicMock()
        mock_executor.check_image_exists.return_value = True
        mock_executor.execute_python_code.return_value = {
            "success": False,
            "output": "",
            "error": "NameError: name 'undefined_var' is not defined\n",
            "exit_code": 1
        }
        mock_executor_class.return_value = mock_executor

        with mock_webui_user(id="test_user_1"):
            # Create a session
            create_response = self.fast_api_client.post(self.create_url("/sessions"))
            session_id = create_response.json()["id"]
            
            # Execute code with error
            execute_response = self.fast_api_client.post(
                self.create_url(f"/sessions/{session_id}/execute"),
                json={"code": "print(undefined_var)"}
            )
        
        assert execute_response.status_code == 200
        data = execute_response.json()
        assert data["success"] is False
        assert "NameError" in data["error"]
        assert data["exit_code"] == 1

    @patch("open_webui.routers.code.DockerCodeExecutor")
    def test_execute_code_session_not_found(self, mock_executor_class):
        """Test executing code on a non-existent session"""
        with mock_webui_user(id="test_user_1"):
            response = self.fast_api_client.post(
                self.create_url("/sessions/nonexistent_id/execute"),
                json={"code": "print('Hello')"}
            )
        
        assert response.status_code == 404

    @patch("open_webui.routers.code.DockerCodeExecutor")
    def test_execute_code_forbidden(self, mock_executor_class):
        """Test executing code on a session that belongs to another user"""
        # Create a session as user 1
        with mock_webui_user(id="test_user_1"):
            create_response = self.fast_api_client.post(self.create_url("/sessions"))
            session_id = create_response.json()["id"]
        
        # Try to execute code as user 2
        with mock_webui_user(id="test_user_2"):
            response = self.fast_api_client.post(
                self.create_url(f"/sessions/{session_id}/execute"),
                json={"code": "print('Hello')"}
            )
        
        assert response.status_code == 403
