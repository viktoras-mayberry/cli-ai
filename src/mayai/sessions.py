"""Session persistence — save and load conversation history to disk."""

import json
from datetime import datetime
from pathlib import Path

from .config import CONFIG_DIR

SESSIONS_DIR = CONFIG_DIR / "sessions"


def _sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def _session_path(name: str) -> Path:
    return _sessions_dir() / f"{name}.json"


def save_session(
    name: str,
    provider: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
) -> Path:
    """Write a session to disk. Returns the file path."""
    data = {
        "name": name,
        "provider": provider,
        "model": model,
        "system_prompt": system_prompt,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "messages": messages,
    }
    path = _session_path(name)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_session(name: str) -> dict:
    """Load a session from disk. Raises FileNotFoundError if not found."""
    path = _session_path(name)
    if not path.exists():
        raise FileNotFoundError(f"No session named '{name}'.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def list_sessions() -> list[dict]:
    """Return metadata for all saved sessions, newest first."""
    sessions = []
    for path in _sessions_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append({
                "name": data.get("name", path.stem),
                "provider": data.get("provider", "?"),
                "model": data.get("model", "?"),
                "saved_at": data.get("saved_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return sorted(sessions, key=lambda s: s["saved_at"], reverse=True)


def delete_session(name: str) -> None:
    """Delete a session file. Raises FileNotFoundError if not found."""
    path = _session_path(name)
    if not path.exists():
        raise FileNotFoundError(f"No session named '{name}'.")
    path.unlink()


def auto_name(provider: str) -> str:
    """Generate a timestamped session name."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{provider}-{ts}"
