"""Local file search: find files on the user's system by name, type, date, and content."""

from __future__ import annotations

import fnmatch
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".cache", ".Trash",
    "Library", "AppData", "$Recycle.Bin", "System Volume Information",
}

DEFAULT_MAX_RESULTS = 50


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


def _format_time(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError):
        return "unknown"


def search_files(
    query: str,
    search_paths: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    extensions: list[str] | None = None,
) -> list[dict]:
    """Search for files matching a natural-language-ish query.

    Matching strategy (all case-insensitive):
    - Split query into keywords
    - Match files whose name or parent directory contains any keyword
    - Optionally filter by extension list

    Returns list of dicts with keys: name, path, size, modified, extension.
    """
    if not search_paths:
        home = str(Path.home())
        search_paths = [home]

    keywords = [kw.lower() for kw in re.split(r'\s+', query.strip()) if len(kw) >= 2]
    if not keywords:
        return []

    year_pattern = re.compile(r"20\d{2}")
    year_keywords = [kw for kw in keywords if year_pattern.fullmatch(kw)]
    name_keywords = [kw for kw in keywords if not year_pattern.fullmatch(kw)]

    ext_filter: set[str] | None = None
    if extensions:
        ext_filter = {e.lower().lstrip(".") for e in extensions}

    _EXT_ALIASES = {
        "pdf": {"pdf"}, "word": {"doc", "docx"}, "document": {"doc", "docx", "pdf", "txt"},
        "excel": {"xls", "xlsx"}, "spreadsheet": {"xls", "xlsx", "csv"},
        "image": {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"},
        "photo": {"jpg", "jpeg", "png", "heic"}, "video": {"mp4", "avi", "mov", "mkv"},
        "music": {"mp3", "wav", "flac", "aac"}, "audio": {"mp3", "wav", "flac", "aac"},
        "text": {"txt", "md", "rtf"}, "csv": {"csv"}, "zip": {"zip", "tar", "gz", "7z", "rar"},
    }
    for kw in name_keywords:
        if kw in _EXT_ALIASES:
            if ext_filter is None:
                ext_filter = set()
            ext_filter.update(_EXT_ALIASES[kw])

    results: list[dict] = []

    for base in search_paths:
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

            for fname in filenames:
                if len(results) >= max_results:
                    break

                fname_lower = fname.lower()
                ext = fname_lower.rsplit(".", 1)[-1] if "." in fname_lower else ""

                if ext_filter and ext not in ext_filter:
                    continue

                filepath = os.path.join(dirpath, fname)
                searchable = fname_lower + " " + dirpath.lower()

                name_match = any(kw in searchable for kw in name_keywords) if name_keywords else True

                if not name_match:
                    continue

                try:
                    stat = os.stat(filepath)
                except OSError:
                    continue

                if year_keywords:
                    mod_year = str(datetime.fromtimestamp(stat.st_mtime).year)
                    if not any(yr == mod_year for yr in year_keywords):
                        if not any(yr in fname_lower for yr in year_keywords):
                            continue

                results.append({
                    "name": fname,
                    "path": filepath,
                    "size": _human_size(stat.st_size),
                    "modified": _format_time(stat.st_mtime),
                    "extension": ext,
                })

            if len(results) >= max_results:
                break

    results.sort(key=lambda r: r["name"].lower())
    return results


# ------------------------------------------------------------------ #
# SQLite FTS5 content index                                            #
# ------------------------------------------------------------------ #

_INDEX_DIR = Path.home() / ".config" / "mayai"
_INDEX_DB = _INDEX_DIR / "file_index.db"

_INDEXABLE_EXTENSIONS = {
    ".txt", ".md", ".log", ".rst", ".csv", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".py", ".js", ".ts", ".html", ".css",
    ".xml", ".sql", ".sh", ".bat", ".r",
    # Common documents (optional extractors)
    ".pdf", ".docx", ".xlsx",
}

MAX_FILE_SIZE = 1_000_000  # 1 MB


def _get_index_db() -> sqlite3.Connection:
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_INDEX_DB))
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS file_content "
        "USING fts5(path, name, content, mtime)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS indexed_files "
        "(path TEXT PRIMARY KEY, mtime REAL, size INTEGER)"
    )
    return conn


def index_directory(directory: str, verbose: bool = False) -> int:
    """Walk a directory and index text files into FTS5. Returns count of indexed files."""
    conn = _get_index_db()
    count = 0

    from .extractor import extract_text

    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _INDEXABLE_EXTENSIONS:
                continue

            filepath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(filepath)
            except OSError:
                continue

            if stat.st_size > MAX_FILE_SIZE:
                continue

            row = conn.execute(
                "SELECT mtime FROM indexed_files WHERE path = ?", (filepath,)
            ).fetchone()
            if row and row[0] >= stat.st_mtime:
                continue

            content, _fmt = extract_text(filepath, max_chars=MAX_FILE_SIZE)
            if not content:
                continue

            conn.execute("DELETE FROM file_content WHERE path = ?", (filepath,))
            conn.execute(
                "INSERT INTO file_content (path, name, content, mtime) VALUES (?, ?, ?, ?)",
                (filepath, fname, content, str(stat.st_mtime)),
            )
            conn.execute(
                "INSERT OR REPLACE INTO indexed_files (path, mtime, size) VALUES (?, ?, ?)",
                (filepath, stat.st_mtime, stat.st_size),
            )
            count += 1

            if verbose and count % 100 == 0:
                print(f"  Indexed {count} files...")

    conn.commit()
    conn.close()
    return count


def search_content(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[dict]:
    """Search the FTS5 index for files containing the query text.

    Returns list of dicts with keys: name, path, snippet, size, modified.
    """
    if not _INDEX_DB.exists():
        return []

    conn = _get_index_db()
    fts_query = " ".join(f'"{w}"' for w in query.split() if len(w) >= 2)
    if not fts_query:
        conn.close()
        return []

    try:
        rows = conn.execute(
            "SELECT path, name, "
            "snippet(file_content, 2, '>>>', '<<<', '...', 40) AS snip, "
            "bm25(file_content) AS score "
            "FROM file_content WHERE file_content MATCH ? "
            "ORDER BY score LIMIT ?",
            (fts_query, max_results),
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []

    results: list[dict] = []
    for filepath, name, snippet, score in rows:
        try:
            stat = os.stat(filepath)
            results.append({
                "name": name,
                "path": filepath,
                "snippet": snippet,
                "score": float(score) if score is not None else None,
                "size": _human_size(stat.st_size),
                "modified": _format_time(stat.st_mtime),
            })
        except OSError:
            continue

    conn.close()
    return results


def find_best_matches(query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    """Hybrid search: combine filename search + indexed content search.

    Returns results sorted by relevance, with optional `snippet` for content matches.
    """
    by_path: dict[str, dict] = {}

    # Name/path search (fast, no index required)
    for item in search_files(query, max_results=max_results):
        item = dict(item)
        item["match_type"] = "name"
        by_path[item["path"]] = item

    # Content search (requires index)
    for item in search_content(query, max_results=max_results):
        item = dict(item)
        item["match_type"] = "content"
        existing = by_path.get(item["path"])
        if existing:
            # Prefer content snippet but keep extension if present
            existing["snippet"] = item.get("snippet")
            existing["match_type"] = "content"
            existing["score"] = item.get("score")
        else:
            by_path[item["path"]] = item

    results = list(by_path.values())

    def _sort_key(r: dict):
        # Content matches first; then lower bm25 score (more relevant); then name
        is_content = 0 if r.get("match_type") == "content" else 1
        score = r.get("score")
        score_key = score if isinstance(score, (int, float)) else 1e9
        return (is_content, score_key, str(r.get("name", "")).lower())

    results.sort(key=_sort_key)
    return results[:max_results]
