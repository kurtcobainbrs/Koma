"""Remember saved document paths independently of recovery and project content."""
import json
from pathlib import Path
from koma.paths import atomic_json


def read_session(directory):
    try:
        raw = json.loads((Path(directory) / 'last-session.json').read_text(encoding='utf-8'))
        if raw.get('version') != 1 or not isinstance(raw.get('paths'), list):
            return ()
        return tuple(Path(value) for value in raw['paths'][:100]
            if isinstance(value, str) and Path(value).suffix.lower() == '.koma')
    except (OSError, ValueError, AttributeError):
        return ()


def write_session(directory, paths):
    atomic_json(Path(directory) / 'last-session.json', {'version': 1,
        'paths': list(dict.fromkeys(str(path) for path in paths if path))[:100]})
