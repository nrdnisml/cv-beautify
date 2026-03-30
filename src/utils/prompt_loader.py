from pathlib import Path
from functools import lru_cache

class PromptLoader:
    def __init__(self):
        self.base_path = Path(__file__).resolve().parent.parent / "prompts"

    @lru_cache(maxsize=64)
    def load(self, category: str, name: str) -> str:
        file_path = self.base_path / category / f"{name}.txt"

        if not file_path.exists():
            raise FileNotFoundError(f"{category} prompt not found: {file_path}")

        return file_path.read_text(encoding="utf-8").strip()