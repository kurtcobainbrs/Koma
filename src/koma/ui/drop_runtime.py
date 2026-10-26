"""Seleciona somente um cliente compilado com o protocolo de drop do Koma."""

import hashlib
import json
import os
from pathlib import Path
import sys

PROTOCOL = 1
FLET_VERSION = '1.0.5'
_enabled = False
_reason = 'Cliente Flet com a extensão de imagens ainda não compilado.'


def development_client(root):
    """Cliente publicado por ponteiro; versões em uso não precisam ser removidas."""
    base = Path(root).resolve() / 'build/koma-flet'
    pointer = base / 'current.json'
    if not pointer.exists():
        return base / 'client'
    metadata = json.loads(pointer.read_text(encoding='utf-8'))
    name = metadata.get('directory') if isinstance(metadata, dict) else None
    if not isinstance(name, str):
        raise ValueError('Ponteiro de cliente inválido.')
    candidate = (base / name).resolve()
    if candidate.parent != base.resolve():
        raise ValueError('O cliente deve estar dentro da pasta de builds do Koma.')
    return candidate


def validate_client(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'koma-client.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('Manifesto inválido do cliente Flet.')
    if manifest.get('protocol') != PROTOCOL or manifest.get('flet') != FLET_VERSION:
        raise ValueError('Cliente Flet incompatível com o protocolo do Koma.')
    files = manifest.get('files')
    required = {'flet.exe', 'flutter_windows.dll', 'data/app.so',
        'data/flutter_assets/fonts/MaterialIcons-Regular.otf'}
    if not isinstance(files, dict) or not required <= files.keys():
        raise ValueError('Manifesto incompleto do cliente Flet.')
    for relative, digest in files.items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError('O cliente Flet está incompleto.')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Arquivo alterado no cliente Flet: {relative}')
    return directory


def configure():
    global _enabled, _reason
    _enabled = False
    if sys.platform != 'win32':
        _reason = 'O cliente de arraste desta distribuição foi compilado para Windows.'
        return False
    if os.environ.get('KOMA_EXTERNAL_DROP') == '0':
        _reason = 'Arraste externo desativado nesta instância.'
        return False
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))
    try:
        explicit = os.environ.get('KOMA_FLET_CLIENT')
        candidate = Path(explicit) if explicit else (root / 'desktop/flet'
            if getattr(sys, 'frozen', False) else development_client(root))
        candidate = validate_client(candidate)
    except (OSError, ValueError, TypeError) as exc:
        _reason = f'Arraste externo indisponível: {exc}. Use Importar imagens.'
        return False
    os.environ['FLET_VIEW_PATH'] = str(candidate)
    _enabled, _reason = True, ''
    return True


def enabled():
    return _enabled


def unavailable_reason():
    return _reason
