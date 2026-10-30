"""Preferências do Storyboard globais, separadas do documento e das cópias."""

import asyncio
import json
from dataclasses import asdict, dataclass, replace
from uuid import uuid4

from pathlib import Path
from koma.editor.shortcuts import default_keymap
from koma.paths import atomic_json


class AppPreferences:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'settings.json'
        from koma.global_preferences import GlobalPreferences
        self.configuration = GlobalPreferences(directory)
        from koma.preview_cache import PreviewCache
        self.preview_cache = PreviewCache(self.configuration.values['system']['cache'])
        self.last_tool = 'select'
        try:
            from koma.editor.drawing_geometry import drawing_tool
            raw = json.loads((self.directory / 'tool-state.json').read_text(encoding='utf-8'))
            self.last_tool = drawing_tool(raw['tool'])
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.saved_tool = self.last_tool
        self.saving_tool = False
        self.shortcuts = default_keymap()
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                raise ValueError('Preferências inválidas.')
            self.shortcuts.restore(raw.get('shortcuts', {}))
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.shortcuts.listeners.append(self.save)

    def save(self):
        atomic_json(self.path, {'version': 1, 'shortcuts': self.shortcuts.export()})

    async def flush_tool(self):
        if self.saving_tool:
            return
        self.saving_tool = True
        try:
            while self.saved_tool != self.last_tool:
                latest = self.last_tool
                await asyncio.to_thread(atomic_json, self.directory / 'tool-state.json', {'version': 1, 'tool': latest})
                self.saved_tool = latest
        except OSError:
            pass  # Tool focus is transient; a failure must never interrupt drawing.
        finally:
            self.saving_tool = False


@dataclass(frozen=True)
class StoryboardOptions:
    show_subtitles: bool = True
    include_subtitles: bool = True
    reference_fields: tuple[str, ...] = ()


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
            from koma.exports.reference_overlay import reference_fields
            values = {key: raw[key] for key, default in asdict(StoryboardOptions()).items()
                if type(default) is bool and type(raw.get(key)) is bool}
            try:
                values['reference_fields'] = reference_fields(raw.get('reference_fields', []))
            except ValueError:
                pass
            return StoryboardOptions(**values)
        except (OSError, ValueError):
            return StoryboardOptions()

    async def load(self):
        self.options = self.saved = await asyncio.to_thread(self.read)

    def update(self, **values):
        from koma.exports.reference_overlay import reference_fields
        if 'reference_fields' in values:
            values['reference_fields'] = reference_fields(values['reference_fields'])
        if any(key not in asdict(self.options) or (key != 'reference_fields' and type(value) is not bool)
               for key, value in values.items()):
            raise ValueError('Preferência do storyboard inválida.')
        options = replace(self.options, **values)
        if options != self.options:
            self.options = options
            if 'reference_fields' in values:
                from koma.global_preferences import freeze
                config = self.view.settings.configuration
                candidate = config.editable()
                for key in candidate['reference']:
                    if type(candidate['reference'][key]) is bool:
                        candidate['reference'][key] = key in values['reference_fields']
                config.publish(freeze(candidate))
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
                await self.view.settings.configuration.persist()
                self.saved = options
            except OSError:
                self.view.notify('Não foi possível salvar as preferências do Koma.', 'warning')
