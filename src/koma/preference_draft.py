"""Separate, versioned storage for the preferences prototype, never runtime settings."""
import json
from copy import deepcopy
from pathlib import Path
from koma.paths import atomic_json
from koma.preference_catalog import defaults, validated


VERSION = 3


def migrate(raw):
    if not isinstance(raw, dict) or raw.get('version') not in (1, 2, VERSION):
        raise ValueError('Versão da prévia inválida.')
    values = deepcopy(raw['values'])
    if raw['version'] == 1:
        numbers = values.pop('numbers', {})
        timeline = values.setdefault('timeline', {})
        for key, value in numbers.items():
            timeline.setdefault(key, value)
    if raw['version'] < 3:
        system = values.setdefault('system', {})
        for section in ('recovery', 'performance'):
            for key, value in values.pop(section, {}).items():
                system.setdefault(key, value)
    return validated(values)


class PreferenceDraft:
    def __init__(self, directory):
        self.path = Path(directory) / 'preferences-preview.json'

    def read(self):
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            return migrate(raw)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass
        return defaults()

    def write(self, values):
        atomic_json(self.path, {'version': VERSION, 'values': validated(values)})
