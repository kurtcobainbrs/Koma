"""Validated global configuration; immutable snapshots isolate ongoing exports."""
import json
import asyncio
from pathlib import Path
from types import MappingProxyType
from koma.paths import atomic_json
from koma.preference_catalog import defaults, validated


def freeze(values):
    return MappingProxyType({key: MappingProxyType(dict(section)) for key, section in values.items()})


def validate_configuration(values):
    candidate = validated(values)
    from koma.editor.guide_geometry import guide_positions
    guide_positions(candidate['guides']['vertical'])
    guide_positions(candidate['guides']['horizontal'])
    from koma.file_defaults import validate_template
    from koma.editor.frame_format import FrameFormat
    from koma.editor.drawing_models import MAX_BRUSH_WIDTH
    validate_template(candidate['files']['filename'])
    for key in ('import_folder', 'export_folder'):
        folder = candidate['files'][key]
        if folder and not Path(folder).expanduser().is_absolute():
            raise ValueError('Escolha uma pasta com caminho completo.')
    FrameFormat(candidate['projects']['width'], candidate['projects']['height']).validate()
    if candidate['projects']['fps'] not in (24, 25, 30, 60):
        raise ValueError('Escolha 24, 25, 30 ou 60 FPS.')
    if candidate['drawing']['width'] > MAX_BRUSH_WIDTH:
        raise ValueError(f'A espessura máxima é {MAX_BRUSH_WIDTH} px.')
    return candidate


class GlobalPreferences:
    def __init__(self, directory):
        self.path = Path(directory) / 'preferences.json'
        self.listeners = []
        self.revision = 0
        self.lock = asyncio.Lock()
        values = defaults()
        if not self.path.exists():
            try:
                legacy = json.loads((Path(directory) / 'options.json').read_text(encoding='utf-8'))
                fields = legacy.get('reference_fields', [])
                if isinstance(fields, list):
                    values['reference'].update({key: key in fields for key in values['reference']
                        if type(values['reference'][key]) is bool})
            except (OSError, ValueError, AttributeError):
                pass
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if raw.get('version') == 1:
                values = validate_configuration(raw['values'])
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass
        self.values = freeze(values)

    def editable(self):
        return {key: dict(section) for key, section in self.values.items()}

    def write(self, values):
        candidate = validate_configuration(values)
        atomic_json(self.path, {'version': 1, 'values': candidate})
        return freeze(candidate)

    def publish(self, snapshot):
        previous = self.values
        self.values = snapshot
        self.revision += 1
        for listener in tuple(self.listeners):
            listener(previous, snapshot)

    async def commit(self, values):
        async with self.lock:
            snapshot = await asyncio.to_thread(self.write, values)
            self.publish(snapshot)

    async def persist(self):
        async with self.lock:
            await asyncio.to_thread(self.write, self.editable())
