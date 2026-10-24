"""Cria um kit portátil com hashes, auditoria e roteiro, sem embutir dados do usuário."""

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def prepare(root):
    root = Path(root).resolve()
    distribution = root / 'dist/Koma'
    audit = json.loads((root / 'build/windows-native-audit.json').read_text(encoding='utf-8'))
    if audit['errors']:
        raise ValueError('Não é possível empacotar uma distribuição reprovada.')
    for row in audit['native_files']:
        path = distribution / row['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError(f"Binário mudou após a auditoria: {row['file']}")
    entries = [(path, 'Koma/' + path.relative_to(distribution).as_posix())
               for path in sorted(distribution.rglob('*')) if path.is_file()]
    entries += [(root / source, destination) for source, destination in (
        ('scripts/validate_clean_windows.ps1', 'validate_clean_windows.ps1'),
        ('scripts/new_validation_sandbox.ps1', 'new_validation_sandbox.ps1'),
        ('docs/CLEAN_WINDOWS.md', 'LEIA-ME.md'),
        ('build/windows-native-audit.json', 'windows-native-audit.json'),
        ('build/flet-native-policy.json', 'flet-native-policy.json'),
    )]
    destination = root / 'dist/Koma-windows-x64-validation.zip'
    temporary = destination.with_suffix('.zip.tmp')
    manifest = [{'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                for path, name in entries]
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
            for path, name in entries:
                archive.write(path, name)
            archive.writestr('SHA256.json', json.dumps(manifest, indent=2))
        temporary.replace(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n', encoding='ascii')
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Kit: {destination}\nSHA256: {digest}')


if __name__ == '__main__':
    prepare(Path(__file__).resolve().parents[1])
