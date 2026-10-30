"""Gera artefatos de release a partir do pacote Windows já auditado."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import subprocess
import tomllib
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

from koma.ui.drop_runtime import validate_client

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def build(root, compiler, *, notes_path=None, prerelease=True):
    root, compiler = Path(root).resolve(), Path(compiler).resolve()
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    release_version = project['version']
    supplied_notes = Path(notes_path).read_text(encoding='utf-8') if notes_path else None
    if supplied_notes is not None and not supplied_notes.strip():
        raise ValueError('As notas da release estão vazias.')
    if len(release_version.split('.')) != 3 or any(not part.isdecimal() for part in release_version.split('.')):
        raise ValueError('Use uma versão numérica major.minor.patch para o instalador.')
    destination = root / f'dist/releases/v{release_version}'
    if destination.exists():
        raise ValueError('Essa release já existe. Preserve-a e incremente a versão para gerar outra.')
    package = root / 'dist/Koma'
    validate_client(package / '_internal/desktop/flet')
    audit = json.loads((root / 'build/windows-native-audit.json').read_text(encoding='utf-8'))
    diagnostic = json.loads((root / 'build/packaged-diagnostics.json').read_text(encoding='utf-8'))
    if audit.get('errors') or not audit.get('native_files') or not diagnostic.get('ok') or not diagnostic.get('frozen'):
        raise ValueError('O pacote precisa passar na auditoria e no diagnóstico antes da release.')
    for item in audit['native_files']:
        path = (package / item['file']).resolve()
        if not path.is_relative_to(package) or sha256(path) != item['sha256']:
            raise ValueError('Um binário mudou após a auditoria.')
    if not compiler.is_file():
        raise ValueError('Informe o ISCC.exe do Inno Setup 6.')
    stage = root / f'build/release-stage-{uuid4().hex}'
    stage.mkdir(parents=True)
    installer_name = f'Koma-{release_version}-windows-x64-setup.exe'
    subprocess.run([str(compiler), f'/DAppVersion={release_version}', f'/DPackageDir={package}',
        f'/DReleaseDir={stage}', f'/DAppIcon={root / "src/koma/assets/koma.ico"}',
        str(root / 'packaging/windows/installer.iss')], check=True)
    installer = stage / installer_name
    if not installer.is_file() or installer.stat().st_size < 1_000_000:
        raise ValueError('O instalador não foi gerado corretamente.')
    portable_name = f'Koma-{release_version}-windows-x64-portable.zip'
    file_manifest = []
    with ZipFile(stage / portable_name, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                relative = path.relative_to(package).as_posix()
                archive.write(path, f'Koma/{relative}')
                file_manifest.append(dict(path=relative, sha256=sha256(path), bytes=path.stat().st_size))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip())
    metadata = dict(version=release_version, tag=f'v{release_version}', prerelease=prerelease,
        created_utc=datetime.now(timezone.utc).isoformat(), platform='Windows x64',
        source_git_head=commit, source_dirty=dirty,
        runtime={name: version(name) for name in ('flet', 'flet-desktop', 'miniaudio', 'pillow', 'reportlab', 'pyinstaller')},
        native_binary_count=len(audit['native_files']), installer_signed=False, files=file_manifest)
    (stage / 'build-info.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    notes = supplied_notes or f'''# Koma {release_version} — {'prévia' if prerelease else 'release'} para Windows

Editor de storyboard e animatic para Windows.

## Instalar

Baixe **{installer_name}** e execute no Windows 10/11 x64.
A instalação é por usuário, sem solicitar administrador. Python não é necessário.
O instalador oferece atalhos opcionais e a opção de adicionar o Koma ao menu Abrir com.
Use a variante portable para executar sem instalar; extraia a pasta inteira antes de abrir Koma.exe.

## Incluído

- Canvas de quadros com cenas, conexões, imagens, enquadramento e histórico.
- Timeline compacta com agulha, zoom, duração em frames/segundos e expressões.
- Áudio por cena, waveform, marcadores e atalhos de reprodução/edição.
- Arraste de imagens e abertura de projetos .koma por soltura na janela.
- Projetos portáteis, recuperação local e exportação PDF e MP4.

## Observações desta prévia

- O MP4 é gerado pelo próprio aplicativo, sem instalar programas adicionais.
- Projetos antigos abrem; novos salvamentos usam o formato atual, que clientes antigos podem não abrir.
- O instalador ainda não tem assinatura digital de publicação.
- A homologação em uma máquina Windows limpa permanece pendente.
- O arraste da própria trilha de áudio ainda não faz parte desta versão; use Início (frames).

Os hashes estão em SHA256SUMS.txt. Os avisos de terceiros acompanham o aplicativo em _internal/licenses.
'''
    (stage / 'RELEASE-NOTES.md').write_text(notes, encoding='utf-8')
    (stage / 'SHA256SUMS.txt').write_text(''.join(f'{sha256(path)}  {path.name}\n'
        for path in sorted(stage.iterdir()) if path.is_file()), encoding='ascii')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage.rename(destination)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--iscc', type=Path, default=ROOT / 'build/tools/inno-6.7.3/ISCC.exe')
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--stable', action='store_true')
    args = parser.parse_args()
    print(build(ROOT, args.iscc, notes_path=args.notes, prerelease=not args.stable))
