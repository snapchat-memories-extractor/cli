import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import Config  # noqa: E402
from src.metadata.json_memory_loader import Memory, load_json_memories  # noqa: E402
from src.metadata.media_datetime_reader import MediaDatetimeReader  # noqa: E402

MATCH_PREFIX = "Could not match media file to JSON memory by datetime: "


def main() -> int:
    args = _parse_args()
    log_path = args.log_path or _latest_log_path(args.logs_dir)
    raw_paths = _logged_match_paths(log_path, limit=args.limit)

    if not raw_paths:
        print(f"No MATCH failures found in {log_path}")
        return 1

    memories = _load_memories(args.memories_json)
    memories_by_datetime = _group_memories_by_datetime(memories)

    print(f"latest log: {log_path}")
    print(f"memories json: {args.memories_json}")
    print(f"output folder: {args.output_folder}")

    for index, raw_path in enumerate(raw_paths, start=1):
        media_path = _resolve_media_path(raw_path, args.output_folder)
        media_datetime = MediaDatetimeReader(media_path).run()

        print(f"\nMATCH FAILURE {index}")
        print(f"logged path: {raw_path}")
        print(f"resolved path: {media_path}")
        print(f"media mtime local: {_format_local_mtime(media_path)}")
        print(
            "media datetime from production reader: "
            f"{_format_datetime(media_datetime)}",
        )

        exact_matches = memories_by_datetime.get(media_datetime, [])
        print(f"exact loaded JSON matches: {len(exact_matches)}")
        for memory in exact_matches[:5]:
            print(f"  exact: {_format_memory(memory)}")

        print("nearest loaded JSON datetimes:")
        for memory in _nearest_memories(media_datetime, memories):
            delta_seconds = int((memory.captured_at - media_datetime).total_seconds())
            print(f"  delta={delta_seconds:+}s {_format_memory(memory)}")

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print two media-vs-JSON datetime matcher failures from the latest log."
        ),
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=ROOT / "logs",
        help="Folder containing JSONL logs. Defaults to ./logs.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help="Specific JSONL log to inspect. Defaults to newest in --logs-dir.",
    )
    parser.add_argument(
        "--memories-json",
        type=Path,
        default=ROOT / "data" / "memories_history.json",
        help="Snapchat memories_history.json path. Defaults to ./data.",
    )
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=ROOT / "output",
        help="Folder containing downloaded media. Defaults to ./output.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Number of MATCH failures to print. Defaults to 2.",
    )
    return parser.parse_args()


def _latest_log_path(logs_dir: Path) -> Path:
    if not logs_dir.exists():
        _fail(f"No logs folder found at {logs_dir}")

    log_paths = sorted(
        logs_dir.glob("*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not log_paths:
        _fail(f"No .jsonl logs found in {logs_dir}")

    return log_paths[0]


def _logged_match_paths(log_path: Path, limit: int) -> list[Path]:
    paths = []
    with log_path.open(encoding="utf-8") as file:
        for line in file:
            item = json.loads(line)
            message = item.get("message", "")
            if item.get("error_code") != "MATCH":
                continue
            if not message.startswith(MATCH_PREFIX):
                continue

            paths.append(Path(message.removeprefix(MATCH_PREFIX)))
            if len(paths) == limit:
                return paths

    return paths


def _load_memories(memories_json: Path) -> list[Memory]:
    if not memories_json.exists():
        _fail(f"No memories JSON found at {memories_json}")

    Config.json_path = memories_json
    Config.cli_options = {
        "strict_location": False,
        "ffmpeg_timeout": 60,
    }
    return load_json_memories()


def _group_memories_by_datetime(memories: list[Memory]) -> dict[datetime, list[Memory]]:
    grouped = defaultdict(list)
    for memory in memories:
        grouped[memory.captured_at].append(memory)
    return grouped


def _resolve_media_path(raw_path: Path, output_folder: Path) -> Path:
    candidates = [
        raw_path,
        ROOT / raw_path,
        output_folder / raw_path.name,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return _fail(f"Logged media file not found: {raw_path}")


def _nearest_memories(
    media_datetime: datetime | None,
    memories: list[Memory],
    limit: int = 5,
) -> list[Memory]:
    if media_datetime is None:
        return []

    return sorted(
        memories,
        key=lambda memory: abs((memory.captured_at - media_datetime).total_seconds()),
    )[:limit]


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "None"


def _format_local_mtime(path: Path) -> str:
    mtime_utc = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return mtime_utc.astimezone().replace(microsecond=0).isoformat()


def _format_memory(memory: Memory) -> str:
    return (
        f"json datetime={memory.captured_at.astimezone(UTC).isoformat()} "
        f"coords={memory.location_coords}"
    )


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    raise SystemExit(main())
