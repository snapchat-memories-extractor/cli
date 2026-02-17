from dataclasses import dataclass
from pathlib import Path

from src.config.cli_args import get_cli_args
from src.config.cli_options import build_cli_options
from src.config.paths import ensure_directories


@dataclass
class Config:
    json_path: Path = None
    downloads_folder: Path = Path("downloads")
    logs_folder: Path = Path("logs")
    cli_options: dict = None

    def __post_init__(self) -> None:
        ensure_directories(self.downloads_folder, self.logs_folder)

    @classmethod
    def initialize_config(cls) -> None:
        args = get_cli_args()
        cls.cli_options = build_cli_options(args)
        cls.json_path = cls.get_memories_json_path()
        cls._ensure_directories()

    @classmethod
    def get_memories_json_path(cls) -> Path:
        if cls.cli_options["memories_json"]:
            return Path(cls.cli_options["memories_json"])
        return Path("data/memories_history.json")

    @classmethod
    def _ensure_directories(cls) -> None:
        cls.downloads_folder.mkdir(parents=True, exist_ok=True)
        cls.logs_folder.mkdir(parents=True, exist_ok=True)
