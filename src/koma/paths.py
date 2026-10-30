"""Diretórios do Koma e gravação local atômica."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from platformdirs import user_data_path


def data_directory():
    override = os.environ.get('KOMA_DATA_DIR')
    return Path(override).expanduser().resolve() if override else user_data_path('Koma', appauthor=False)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{uuid4().hex}.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def initial_directory(value='', root=''):
    for candidate in (value, root):
        if not candidate:
            continue
        try:
            path = Path(candidate).expanduser().resolve()
            for directory in (path, *path.parents):
                if directory.is_dir():
                    return str(directory)
        except (OSError, ValueError, RuntimeError):
            continue
    return None


def open_file(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f'O arquivo não existe: {path}')
    _open_path(path)


def open_directory(path):
    path = Path(path).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    _open_path(path)


def _open_path(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
