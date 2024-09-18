from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Configs:
    categories: str = field(default="(cat:cs.CV OR cat:cs.AI OR cat:cs.LG)")
    num_retries: int = field(default=10)
    keywords: Dict[str, List[str]] = field(default_factory=dict)
    datetime: str = field(default=None)
    output_directory: str = field(default="outputs")
    markdown_directory: str = field(default="markdown")
    query: str = field(default=None)
    translate: bool = field(default=False)
    model: str = field(default="")
    batch_mode: bool = field(default=False)
