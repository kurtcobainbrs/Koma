"""Preferências do Storyboard globais, separadas do documento e das cópias."""

import asyncio
import json
from dataclasses import asdict, dataclass, replace
from uuid import uuid4

from pathlib import Path
from koma.blender import detect_blender
from koma.editor.shortcuts import default_keymap
from koma.paths import atomic_json


class AppPreferences:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'settings.json'
        self.shortcuts = default_keymap()
        self.blender = ''
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                raise ValueError('Preferências inválidas.')
            self.blender = raw.get('blender', '') if isinstance(raw.get('blender', ''), str) else ''
            self.shortcuts.restore(raw.get('shortcuts', {}))
        except (OSError, ValueError, TypeError, KeyError):
            pass
        if not self.blender:
            self.blender = detect_blender()
        self.shortcuts.listeners.append(self.save)

    def save(self):
        atomic_json(self.path, {'version': 1, 'blender': self.blender, 'shortcuts': self.shortcuts.export()})


@dataclass(frozen=True)
class StoryboardOptions:
    show_subtitles: bool = True
    include_subtitles: bool = True


class StoryboardPreferences:
    def __init__(self, view):
        self.view = view
        self.path = view.settings.directory / 'options.json'
        self.options = self.saved = StoryboardOptions()
        self.lock = asyncio.Lock()

    def read(self):
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict) or raw.get('version') != 1:
                return StoryboardOptions()
            values = {key: raw[key] for key in asdict(StoryboardOptions()) if type(raw.get(key)) is bool}
            return StoryboardOptions(**values)
        except (OSError, ValueError):
            return StoryboardOptions()

    async def load(self):
        self.options = self.saved = await asyncio.to_thread(self.read)

    def update(self, **values):
        if any(key not in asdict(self.options) or type(value) is not bool for key, value in values.items()):
            raise ValueError('Preferência do storyboard inválida.')
        options = replace(self.options, **values)
        if options != self.options:
            self.options = options
            self.view.page.run_task(self.flush)

    def write(self, options):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f'.{uuid4().hex}.tmp')
        try:
            temporary.write_text(json.dumps({'version': 1, **asdict(options)}), encoding='utf-8')
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    async def flush(self):
        async with self.lock:
            options = self.options
            if options == self.saved:
                return
            try:
                await asyncio.to_thread(self.write, options)
                self.saved = options
            except OSError:
                self.view.notify('Não foi possível salvar as opções de legendas do Koma.', 'warning')
