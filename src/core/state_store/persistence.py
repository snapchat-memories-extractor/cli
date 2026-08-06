import hashlib
import json
import os
from contextlib import suppress
from pathlib import Path

from src.config import Config
from src.config.defaults import APP_STATE_DIR, PIPELINE_STATE_FILE_PREFIX
from src.logger import log


def empty_state() -> dict[str, object]:
    return {"files": {}}


def default_state_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    source_folder = Path(
        Config.cli_options["memories_folder"] or project_root / "data/memories"
    )

    source_path = os.path.normcase(str(source_folder.expanduser().absolute())) # Get string of absolute path
    source_key = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16] # Use first 16 chars of SHA256 hash of path as key
    state_dir = project_root / APP_STATE_DIR # Get the state directory relative to this file

    return state_dir / f"{PIPELINE_STATE_FILE_PREFIX}-{source_key}.json"


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return empty_state()

    raw_text = None
    with suppress(OSError):
        raw_text = path.read_text(encoding="utf-8")

    if raw_text is None:
        log(
            f"Could not read pipeline state file, starting fresh: {path}",
            "warning",
        )
        return empty_state()

    raw_state = None
    with suppress(json.JSONDecodeError):
        raw_state = json.loads(raw_text)

    if not isinstance(raw_state, dict):
        log(
            f"Could not parse pipeline state file, starting fresh: {path}",
            "warning",
        )
        return empty_state()

    files = raw_state.get("files")
    if not isinstance(files, dict):
        log(
            f"Pipeline state file had invalid shape, starting fresh: {path}",
            "warning",
        )
        return empty_state()

    return {"files": files}


def save_state(path: Path, state: dict[str, object]) -> None:
    temp_path = path.with_name(f"{path.name}.tmp")
    saved = False

    with suppress(OSError, TypeError):
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(state, indent=2, sort_keys=True)
        temp_path.write_text(f"{serialized}\n", encoding="utf-8")
        temp_path.replace(path)
        saved = True

    if not saved:
        log(f"Could not save pipeline state file: {path}", "warning")


def delete_state_file(path: Path) -> None:
    if not path.exists():
        return

    deleted = False
    with suppress(OSError):
        path.unlink()
        deleted = True

    if deleted:
        log(f"Deleted pipeline state file: {path}", "info")
    else:
        log(f"Could not delete pipeline state file: {path}", "warning")
