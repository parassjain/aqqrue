import requests

API_BASE = "http://localhost:8000/api"


class APIClient:
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url

    def create_session(self) -> str:
        resp = requests.post(f"{self.base_url}/session/create")
        resp.raise_for_status()
        return resp.json()["session_id"]

    def upload_csv(self, session_id: str, file_bytes: bytes, filename: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/session/{session_id}/upload",
            files={"file": (filename, file_bytes, "text/csv")},
        )
        resp.raise_for_status()
        return resp.json()

    def chat(self, session_id: str, message: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/session/{session_id}/chat",
            json={"message": message},
        )
        resp.raise_for_status()
        return resp.json()

    def undo(self, session_id: str) -> dict:
        resp = requests.post(f"{self.base_url}/session/{session_id}/undo")
        resp.raise_for_status()
        return resp.json()

    def download_csv(self, session_id: str) -> bytes:
        resp = requests.get(f"{self.base_url}/session/{session_id}/download")
        resp.raise_for_status()
        return resp.content

    def get_history(self, session_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/session/{session_id}/history")
        resp.raise_for_status()
        return resp.json()
