"""Abstract base for storage adapters."""

from abc import ABC, abstractmethod
from pathlib import Path
class BaseAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def save(self, note: dict) -> str:
        """Save a note. Returns an identifier for the saved note."""
        ...

    @abstractmethod
    def list_notes(self, intent_filter: str | None = None) -> list[dict]:
        """List all notes, optionally filtered by intent.

        Each dict must include at least: title, intent, created_at, tags,
        and an _file key for identifying the note.
        """
        ...

    @abstractmethod
    def search(self, keyword: str) -> list[dict]:
        """Search notes by keyword (titles and tags minimum)."""
        ...

    @abstractmethod
    def read_note(self, identifier: str) -> dict | None:
        """Read a full note by its identifier. Returns dict with frontmatter
        fields plus _body and context_digest, or None if not found."""
        ...

    @abstractmethod
    def delete(self, identifier: str) -> bool:
        """Delete a note by identifier. Returns True on success."""
        ...
