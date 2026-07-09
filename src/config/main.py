from pathlib import Path

from src.config.cli_args import get_cli_args
from src.config.cli_options import build_cli_options
from src.config.paths import ensure_directories


class Config:
    json_path: Path = None
    memories_folder: Path = None
    output_folder: Path = None
    logs_folder: Path = None
    failures_folder: Path = None
    cli_options: dict = None

    @classmethod
    def initialize_config(cls) -> None:
        args = get_cli_args()
        cls.cli_options = build_cli_options(args)
        cls.json_path = cls._get_memories_json_path()
        cls.memories_folder = cls._get_memories_folder()
        cls.output_folder = cls._get_output_folder()
        cls.logs_folder = cls._get_logs_folder()
        cls.failures_folder = cls._get_failures_folder()
        ensure_directories(cls.output_folder, cls.logs_folder)

    @classmethod
    def _get_memories_json_path(cls) -> Path:
        if cls.cli_options["memories_json"]:
            return Path(cls.cli_options["memories_json"])
        return Path("data/memories_history.json")

    @classmethod
    def _get_memories_folder(cls) -> Path:
        if cls.cli_options["memories_folder"]:
            return Path(cls.cli_options["memories_folder"])
        return Path("data/memories")

    @classmethod
    def _get_output_folder(cls) -> Path:
        if cls.cli_options["output"]:
            return Path(cls.cli_options["output"])
        return Path("downloads")

    @classmethod
    def _get_logs_folder(cls) -> Path:
        if cls.cli_options["logs_path"]:
            return Path(cls.cli_options["logs_path"])
        return Path("logs")

    @classmethod
    def _get_failures_folder(cls) -> Path:
        return cls.memories_folder / ".failures"
