"""File operations: move, rename, copy, delete with preview and confirmation."""

from __future__ import annotations

import os
import platform
import subprocess
import shutil
from pathlib import Path

from .display import print_file_operation_preview, print_info, print_error, print_success, print_warning


def _confirm(prompt: str = "Proceed? [y/N] ") -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def move_files(sources: list[str], dest_dir: str, *, auto_confirm: bool = False) -> list[str]:
    """Move files to a destination directory. Returns list of moved paths.

    Creates the destination directory if it does not exist.
    Shows a preview and asks for confirmation unless auto_confirm is True.
    """
    dest = Path(dest_dir)
    operations = []
    for src in sources:
        src_path = Path(src)
        if not src_path.exists():
            print_warning(f"Skipping (not found): {src}")
            continue
        target = dest / src_path.name
        operations.append({
            "action": "move",
            "source": str(src_path),
            "dest": str(target),
        })

    if not operations:
        print_warning("No valid files to move.")
        return []

    print_file_operation_preview(operations)

    if not dest.exists():
        print_info(f"Directory '{dest}' will be created.")

    if not auto_confirm and not _confirm():
        print_info("Cancelled.")
        return []

    dest.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for op in operations:
        try:
            shutil.move(op["source"], op["dest"])
            moved.append(op["dest"])
        except Exception as exc:
            print_error(f"Failed to move {op['source']}: {exc}")

    if moved:
        print_success(f"Moved {len(moved)} file(s) to {dest}")
    return moved


def rename_file(source: str, new_name: str, *, auto_confirm: bool = False) -> str | None:
    """Rename a file. Returns the new path or None if cancelled/failed."""
    src = Path(source)
    if not src.exists():
        print_error(f"File not found: {source}")
        return None

    target = src.parent / new_name
    if target.exists():
        print_error(f"A file named '{new_name}' already exists in {src.parent}")
        return None

    print_file_operation_preview([{
        "action": "rename",
        "source": str(src),
        "dest": str(target),
    }])

    if not auto_confirm and not _confirm():
        print_info("Cancelled.")
        return None

    try:
        src.rename(target)
        print_success(f"Renamed to: {target}")
        return str(target)
    except Exception as exc:
        print_error(f"Rename failed: {exc}")
        return None


def copy_file(source: str, dest: str, *, auto_confirm: bool = False) -> str | None:
    """Copy a file. Returns new path or None."""
    src = Path(source)
    if not src.exists():
        print_error(f"File not found: {source}")
        return None

    dst = Path(dest)
    if dst.is_dir():
        dst = dst / src.name

    print_file_operation_preview([{
        "action": "copy",
        "source": str(src),
        "dest": str(dst),
    }])

    if not auto_confirm and not _confirm():
        print_info("Cancelled.")
        return None

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        print_success(f"Copied to: {dst}")
        return str(dst)
    except Exception as exc:
        print_error(f"Copy failed: {exc}")
        return None


def copy_to_desktop(source: str, *, auto_confirm: bool = False) -> str | None:
    """Copy a file to the user's Desktop. Returns new path or None."""
    src = Path(source)
    if not src.exists():
        print_error(f"File not found: {source}")
        return None
    desktop = Path.home() / "Desktop"
    return copy_file(str(src), str(desktop), auto_confirm=auto_confirm)


def open_in_default_app(filepath: str) -> bool:
    """Open a file with the OS default app (outside the terminal)."""
    path = Path(filepath)
    if not path.exists():
        print_error(f"File not found: {filepath}")
        return False

    try:
        system = platform.system().lower()
        if system.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
        if system == "darwin":
            subprocess.run(["open", str(path)], check=False)
            return True
        # linux / other
        subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except Exception as exc:  # noqa: BLE001
        print_error(f"Could not open file: {exc}")
        return False


def delete_file(source: str, *, auto_confirm: bool = False) -> bool:
    """Delete a file with extra-cautious confirmation. Returns True on success."""
    src = Path(source)
    if not src.exists():
        print_error(f"File not found: {source}")
        return False

    print_warning(f"This will permanently delete: {src}")
    print_warning(f"  Size: {src.stat().st_size:,} bytes")

    if not auto_confirm:
        try:
            ans = input("Type 'yes' to confirm deletion: ").strip().lower()
            if ans != "yes":
                print_info("Cancelled.")
                return False
        except (EOFError, KeyboardInterrupt):
            return False

    try:
        src.unlink()
        print_success(f"Deleted: {src}")
        return True
    except Exception as exc:
        print_error(f"Delete failed: {exc}")
        return False
