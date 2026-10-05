from src.config import Config
from src.logger import log


def fail_fast_checks() -> bool:
    all_paths_ok = True

    if Config.cli_options["write_metadata"] and not Config.json_path.exists():
        log(f"Missing memories JSON file at {Config.json_path}", "error", "MISS")
        all_paths_ok = False

    if not Config.memories_folder.exists():
        log(f"Missing memories folder at {Config.memories_folder}", "error", "MISS")
        all_paths_ok = False

    if _output_overlaps_memories_folder():
        log(
            "Output directory must be separate from the memories folder. "
            f"Refusing to write output under {Config.memories_folder}: "
            f"{Config.output_folder}",
            "error",
            "MISS",
        )
        all_paths_ok = False

    return all_paths_ok


def _output_overlaps_memories_folder() -> bool:
    memories_folder = Config.memories_folder.expanduser().resolve(strict=False)
    output_folder = Config.output_folder.expanduser().resolve(strict=False)

    return output_folder == memories_folder or output_folder.is_relative_to(
        memories_folder
    )
