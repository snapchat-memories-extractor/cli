from dataclasses import dataclass
from pathlib import Path

from src.config.cli_args import get_cli_args
from src.config.cli_options import build_cli_options
from src.config.paths import _ensure_directories


@dataclass
class Config:
    json_path: Path = None
    output_folder: Path = Path("output")
    logs_folder: Path = None
    cli_options: dict = None

    def __post_init__(self) -> None:
        _ensure_directories(self.output_folder, self.logs_folder)

    @classmethod
    def initialize_config(cls) -> None:
        args = get_cli_args()
        cls.cli_options = build_cli_options(args)
        cls.json_path = cls._get_memories_json_path()
        cls.output_folder = cls._get_output_folder()
        cls.logs_folder = cls._get_logs_folder()
        cls._ensure_directories()

    @classmethod
    def _get_memories_json_path(cls) -> Path:
        if cls.cli_options["memories_json"]:
            return Path(cls.cli_options["memories_json"])
        return Path("data/memories_history.json")

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
    def _ensure_directories(cls) -> None:
        cls.output_folder.mkdir(parents=True, exist_ok=True)
        cls.logs_folder.mkdir(parents=True, exist_ok=True)
