"""Bounded recent-document list; independent of editor sessions."""

import json
from pathlib import Path
from koma.paths import atomic_json


class RecentDocuments:
    def __init__(self, directory, limit=15):
        self.path, self.limit = Path(directory) / 'recent.json', limit
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            self.paths = [str(Path(value).resolve()) for value in raw
                if isinstance(value, str) and Path(value).suffix.lower() == '.koma'][:limit] if isinstance(raw, list) else []
        except (OSError, ValueError):
            self.paths = []

    def add(self, path):
        value = str(Path(path).resolve())
        self.paths = [value, *(item for item in self.paths if item.casefold() != value.casefold())][:self.limit]
        self.save()

    def remove(self, path):
        self.paths = [value for value in self.paths if value != path]
        self.save()

    def save(self):
        try:
            atomic_json(self.path, self.paths)
        except OSError:
            pass  # A preference failure must never fail a document save/open.
