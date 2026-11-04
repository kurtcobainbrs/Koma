"""Application-owned last folders, separated by picker purpose and from projects."""
import asyncio
import json
import logging
from pathlib import Path
from koma.paths import atomic_json, initial_directory


class DialogDirectories:
    def __init__(self, directory):
        self.path = Path(directory) / 'dialog-directories.json'
        self.folders = None
        self.lock = asyncio.Lock()

    def read(self):
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            values = raw.get('folders', {}) if raw.get('version') == 1 else {}
            return {key: value for key, value in values.items()
                if isinstance(key, str) and isinstance(value, str)} if isinstance(values, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}

    async def initial(self, purpose, fallback=''):
        async with self.lock:
            if self.folders is None:
                self.folders = await asyncio.to_thread(self.read)
            return await asyncio.to_thread(initial_directory, self.folders.get(purpose, ''), fallback)

    async def remember(self, purpose, selected_file):
        folder = str(Path(selected_file).expanduser().resolve().parent)
        async with self.lock:
            if self.folders is None:
                self.folders = await asyncio.to_thread(self.read)
            if self.folders.get(purpose) == folder:
                return
            self.folders[purpose] = folder
            try:
                await asyncio.to_thread(atomic_json, self.path, {'version': 1, 'folders': self.folders.copy()})
            except OSError as exc:
                logging.getLogger(__name__).warning('Picker folder persistence failed (%s)', type(exc).__name__)
