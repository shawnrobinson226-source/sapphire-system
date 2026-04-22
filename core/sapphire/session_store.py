"""Persistent session storage for Sapphire execution timeline tracking."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SessionStore:
    """Stores operator-scoped execution sessions on disk."""

    def __init__(self, root_dir: Path | str | None = None, *, store_full_trigger: bool = True):
        self.root_dir = Path(root_dir) if root_dir is not None else Path("user") / "sessions"
        self.store_full_trigger = store_full_trigger
        self._lock = threading.Lock()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _session_path(self, session_id: str) -> Path:
        return self.root_dir / f"{session_id}.json"

    @staticmethod
    def _clean_non_empty(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required.")
        return value.strip()

    def _load_session(self, session_id: str) -> dict | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_session(self, session: dict) -> None:
        session_id = self._clean_non_empty(session.get("session_id"), "session_id")
        path = self._session_path(session_id)
        path.write_text(json.dumps(session, ensure_ascii=True, indent=2), encoding="utf-8")

    def create_session(self, operator_id: str) -> dict:
        clean_operator_id = self._clean_non_empty(operator_id, "operator_id")
        session = {
            "session_id": uuid.uuid4().hex,
            "operator_id": clean_operator_id,
            "created_at": self._now_iso(),
            "entries": [],
        }
        with self._lock:
            self._save_session(session)
        return session

    def get_session(self, session_id: str) -> dict | None:
        clean_session_id = self._clean_non_empty(session_id, "session_id")
        with self._lock:
            return self._load_session(clean_session_id)

    def _trigger_field(self, trigger: str) -> dict[str, str]:
        clean_trigger = self._clean_non_empty(trigger, "trigger")
        # Default policy: store full trigger text for operator-scoped session inspection.
        # Deployments with stricter requirements can set store_full_trigger=False and persist only trigger hash.
        if self.store_full_trigger:
            return {"trigger": clean_trigger}
        digest = hashlib.sha256(clean_trigger.encode("utf-8")).hexdigest()[:16]
        return {"trigger_hash": digest}

    def append_entry(self, session_id: str, entry: dict) -> dict:
        clean_session_id = self._clean_non_empty(session_id, "session_id")
        if not isinstance(entry, dict):
            raise ValueError("entry must be a dictionary.")
        with self._lock:
            session = self._load_session(clean_session_id)
            if not session:
                raise ValueError(f"Session not found: {clean_session_id}")
            entries = session.get("entries")
            if not isinstance(entries, list):
                entries = []
                session["entries"] = entries
            entries.append(dict(entry))
            self._save_session(session)
            return session
