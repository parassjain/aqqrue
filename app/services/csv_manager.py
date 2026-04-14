import io
import os
import shutil
import time
from pathlib import Path
from typing import Optional, List, Dict

import pandas as pd

from app.config import settings


class CSVManager:
    """Manages CSV files with version chain and undo support.

    Storage layout:
        data/sessions/{session_id}/v0.csv   ← original upload
        data/sessions/{session_id}/v1.csv   ← after first operation
        data/sessions/{session_id}/meta.json ← version metadata
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_dir = Path(settings.SESSION_DATA_DIR) / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._versions: list[dict] = []

    @property
    def current_version(self) -> int:
        return len(self._versions) - 1

    @property
    def current_csv_path(self) -> Optional[Path]:
        if not self._versions:
            return None
        return self.session_dir / f"v{self.current_version}.csv"

    def load_csv(self, file_bytes: bytes, filename: str = "upload.csv") -> dict:
        """Load initial CSV from user upload. Returns metadata."""
        df = pd.read_csv(io.BytesIO(file_bytes))
        path = self.session_dir / "v0.csv"
        df.to_csv(path, index=False)
        self._versions.append(
            {
                "version": 0,
                "operation": "initial_upload",
                "filename": filename,
                "timestamp": time.time(),
                "rows": len(df),
                "columns": list(df.columns),
            }
        )
        return self.get_metadata()

    def save_version(self, csv_bytes: bytes, operation: str) -> dict:
        """Save a new CSV version after an operation."""
        new_version = self.current_version + 1
        path = self.session_dir / f"v{new_version}.csv"
        path.write_bytes(csv_bytes)

        df = pd.read_csv(io.BytesIO(csv_bytes))
        self._versions.append(
            {
                "version": new_version,
                "operation": operation,
                "timestamp": time.time(),
                "rows": len(df),
                "columns": list(df.columns),
            }
        )
        return self.get_metadata()

    def undo(self) -> Optional[dict]:
        """Undo last operation. Returns metadata of restored version, or None if nothing to undo."""
        if self.current_version <= 0:
            return None
        # Remove latest version file
        latest_path = self.session_dir / f"v{self.current_version}.csv"
        if latest_path.exists():
            latest_path.unlink()
        self._versions.pop()
        return self.get_metadata()

    def get_current_csv_bytes(self) -> Optional[bytes]:
        """Get the current CSV as bytes."""
        path = self.current_csv_path
        if path is None or not path.exists():
            return None
        return path.read_bytes()

    def get_current_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the current CSV as a DataFrame."""
        csv_bytes = self.get_current_csv_bytes()
        if csv_bytes is None:
            return None
        return pd.read_csv(io.BytesIO(csv_bytes))

    def get_version_csv_bytes(self, version: int) -> Optional[bytes]:
        """Get a specific version's CSV bytes."""
        if version < 0 or version > self.current_version:
            return None
        path = self.session_dir / f"v{version}.csv"
        if not path.exists():
            return None
        return path.read_bytes()

    def get_metadata(self) -> dict:
        """Get metadata about the current CSV (for LLM context)."""
        df = self.get_current_dataframe()
        if df is None:
            return {"loaded": False}

        return {
            "loaded": True,
            "version": self.current_version,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "sample_rows": df.to_dict(orient="records"),
            "null_counts": df.isnull().sum().to_dict(),
        }

    def get_history(self) -> list[dict]:
        """Get the full version history."""
        return list(self._versions)

    def cleanup(self):
        """Remove all session data."""
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)
        self._versions.clear()
