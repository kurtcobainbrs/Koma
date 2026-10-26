"""Promove um pacote auditado preservando o anterior e permitindo rollback."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from koma.ui.drop_runtime import validate_client


def publish(root, staged):
    root, staged = Path(root).resolve(), Path(staged).resolve()
    destination = root / 'dist' / 'Koma'
    if not staged.is_relative_to(root / 'build') or staged.name != 'Koma':
        raise ValueError('O pacote de preparação deve estar dentro de build/.')
    if not destination.resolve().is_relative_to(root / 'dist'):
        raise ValueError('Destino fora do diretório de distribuição.')
    validate_client(staged / '_internal/desktop/flet')
    audit = json.loads((root / 'build/windows-native-audit.json').read_text(encoding='utf-8'))
    if audit.get('errors') or not audit.get('native_files'):
        raise ValueError('Auditoria ausente ou reprovada.')
    for row in audit['native_files']:
        path = (staged / row['file']).resolve()
        if not path.is_relative_to(staged) or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('O pacote mudou após a auditoria.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous = destination.parent / ('previous-' + uuid4().hex) / 'Koma'
    if not previous.resolve().is_relative_to(root / 'dist'):
        raise ValueError('Backup fora do diretório de distribuição.')
    backed_up = False
    try:
        if destination.exists():
            previous.parent.mkdir()
            destination.rename(previous)
            backed_up = True
        staged.rename(destination)
    except OSError:
        if backed_up and not destination.exists():
            previous.rename(destination)
        raise
    return destination


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('staged', type=Path)
    args = parser.parse_args()
    print(publish(Path(__file__).resolve().parents[1], args.staged))
