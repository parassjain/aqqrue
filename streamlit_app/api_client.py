import requests

API_BASE = "http://localhost:8000/api"


class APIClient:
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url

    def _check(self, resp: requests.Response) -> None:
        """Raise with full server error detail for 5xx responses."""
        if resp.status_code >= 500:
            try:
                detail = resp.json().get("detail", resp.text)
                if isinstance(detail, dict):
                    msg = detail.get("message", str(detail))
                    tb = detail.get("traceback", "")
                    detail = f"{msg}\n\n{tb}".strip()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"[{resp.status_code}] {detail}")
        resp.raise_for_status()

    def create_session(self) -> str:
        resp = requests.post(f"{self.base_url}/session/create")
        self._check(resp)
        return resp.json()["session_id"]

    def upload_csv(self, session_id: str, file_bytes: bytes, filename: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/session/{session_id}/upload",
            files={"file": (filename, file_bytes, "text/csv")},
        )
        self._check(resp)
        return resp.json()

    def chat(self, session_id: str, message: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/session/{session_id}/chat",
            json={"message": message},
        )
        self._check(resp)
        return resp.json()

    def undo(self, session_id: str) -> dict:
        resp = requests.post(f"{self.base_url}/session/{session_id}/undo")
        self._check(resp)
        return resp.json()

    def download_csv(self, session_id: str) -> bytes:
        resp = requests.get(f"{self.base_url}/session/{session_id}/download")
        self._check(resp)
        return resp.content

    def get_history(self, session_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/session/{session_id}/history")
        self._check(resp)
        return resp.json()
