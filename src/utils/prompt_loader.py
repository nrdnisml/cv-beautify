import os
import re
from pathlib import Path
from functools import lru_cache

class PromptLoader:
    def __init__(self):
        self.basepath = Path(__file__).resolve().parent.parent / "prompts"
        self.domains_dir = self.basepath / "domains"

    @lru_cache(maxsize=64)
    def load(self, category: str, name: str) -> str:
        filepath = self.basepath / category / f"{name}.txt"

        if not filepath.exists():
            raise FileNotFoundError(f"{category} prompt not found: {filepath}")

        return filepath.read_text(encoding="utf-8").strip()

    def get_available_sectors(self) -> list[dict]:
        sectors = []
        if not self.domains_dir.exists():
            return sectors
        
        for filename in os.listdir(self.domains_dir):
            if filename.endswith("_prompt.txt") and filename != "synthesize_domain_prompt.txt":
                key = filename.replace("_prompt.txt", "")
                label = key.replace("_", " ").title()
                sectors.append({"key": key, "label": label})
        return sorted(sectors, key=lambda x: x["label"])
    
    def save_sector_prompt(self, sector_name: str, content:str) -> str:
        filename = f"{sector_name.lower()}_prompt.txt"
        filepath = self.domains_dir / filename
        self.domains_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return sector_name.lower()
    
    def load_domain_prompt(self, sector_key:str) -> str:
        filepath = self.domains_dir / f"{sector_key}_prompt.txt"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return None
    
    def normalize_to_key(self,text: str) -> str:
        """
        Convert string like 'Oil and Gas' → 'oil_and_gas'
        Safe for filenames, keys, and identifiers.
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Replace non-alphanumeric (including spaces) with underscore
        text = re.sub(r'[^a-z0-9]+', '_', text)

        # Remove leading/trailing underscores
        text = text.strip('_')

        return text