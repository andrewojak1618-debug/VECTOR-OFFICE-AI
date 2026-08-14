from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryEntry:
    id: int
    content: str
    category: str
    source: str
    created_at: str
