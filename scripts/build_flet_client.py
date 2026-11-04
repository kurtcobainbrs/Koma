"""Build reproduzível do cliente; publica somente depois de analyze/test/build."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / 'flutter' / 'client'
EXTENSION = ROOT / 'flutter' / 'koma_drop'

FLUTTER_VERSION = '3.44.8'


def source_fingerprint(root):
    root = Path(root).resolve()
    digest = hashlib.sha256(FLUTTER_VERSION.encode())
    excluded = {'build', '.dart_tool', '.idea', 'ephemeral', '.git'}
    suffixes = {'.dart', '.yaml', '.lock', '.cpp', '.cc', '.h', '.txt', '.rc', '.manifest', '.ico', '.cmake'}
    sources = [root / 'scripts/build_flet_client.py', root / 'scripts/flet_compat.py']
    for directory in (root / 'flutter/client', root / 'flutter/koma_drop', root / 'flutter/compat'):
        for parent, dirs, files in os.walk(directory, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in excluded)
            sources.extend(Path(parent) / name for name in sorted(files) if Path(name).suffix in suffixes)
    for path in sorted(sources):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def cached_client(root):
    from koma.ui.drop_runtime import development_client, validate_client
    try:
        client = validate_client(development_client(root))
        manifest = json.loads((client / 'koma-client.json').read_text(encoding='utf-8'))
        if manifest.get('source_fingerprint') == source_fingerprint(root):
            return client
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return None


def publish_client(staging):
    from koma.paths import atomic_json
    from koma.ui.drop_runtime import validate_client
    staging = validate_client(staging)
    base = ROOT / 'build/koma-flet'
    if staging.parent != base.resolve():
        raise ValueError('O cliente deve estar na pasta de builds do projeto.')
    destination = base / f'client-{uuid4().hex}'
    staging.rename(destination)
    atomic_json(base / 'current.json', {'directory': destination.name})
    return destination


def run(flutter, args, cwd):
    subprocess.run([str(flutter), *args], cwd=cwd, check=True)


def resolve(flutter, directory):
    result = subprocess.run([str(flutter), 'pub', 'get', '--enforce-lockfile'], cwd=directory, capture_output=True, text=True)
    if result.returncode and 'requires symlink support' not in result.stdout + result.stderr:
        raise RuntimeError(result.stdout + result.stderr)
    # Flutter accepts NTFS junctions as existing directory links. This keeps
    # builds local without changing Windows Developer Mode or security settings.
    metadata = directory / '.flutter-plugins-dependencies'
    if os.name == 'nt' and (directory / 'windows').is_dir() and metadata.is_file():
        plugins = json.loads(metadata.read_text())['plugins'].get('windows', [])
        link_root = directory / 'windows' / 'flutter' / 'ephemeral' / '.plugin_symlinks'
        link_root.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            link = link_root / plugin['name']
            if not link.exists():
                target = Path(plugin['path']).resolve()
                if any(char in str(link) + str(target) for char in '&|<>^%!\r\n'):
                    raise ValueError('Caminho não suportado para o vínculo de compilação.')
                subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--flutter', type=Path, default=Path.home() / 'flutter/3.44.8/bin/flutter.bat')
    parser.add_argument('--force', action='store_true', help='Recompila mesmo com cache válido.')
    parser.add_argument('--full-tests', action='store_true', help='Executa analyze/test mesmo reutilizando o cliente.')
    args = parser.parse_args()
    cached = None if args.force else cached_client(ROOT)
    if cached and not args.full_tests:
        print(f'Reutilizando cliente validado: {cached}', flush=True)
        return
    flutter = args.flutter.resolve()
    if not flutter.is_file():
        raise SystemExit('Flutter 3.44.8 não encontrado; informe --flutter.')
    sdk = json.loads(subprocess.check_output([str(flutter), '--version', '--machine'], text=True))
    if sdk.get('flutterVersion') != '3.44.8':
        raise SystemExit('Use Flutter 3.44.8, compatível com o cliente Flet 1.0.5 fixado.')
    from flet_compat import prepare, VERSION
    try:
        prepare(ROOT)
    except FileNotFoundError:
        run(flutter, ['pub', 'cache', 'add', 'flet', '--version', VERSION], ROOT)
        prepare(ROOT)
    resolve(flutter, EXTENSION)
    run(flutter, ['analyze', '--no-pub'], EXTENSION)
    if args.full_tests:
        run(flutter, ['test', '--no-pub'], EXTENSION)
    resolve(flutter, CLIENT)
    run(flutter, ['analyze', '--no-pub'], CLIENT)
    if cached:
        print(f'Cliente validado, sem recompilação: {cached}', flush=True)
        return
    run(flutter, ['build', 'windows', '--release', '--no-pub', '--no-tree-shake-icons'], CLIENT)
    release = CLIENT / 'build/windows/x64/runner/Release'
    staging = ROOT / 'build/koma-flet' / f'staging-{uuid4().hex}'
    shutil.copytree(release, staging)
    icons = staging / 'data/flutter_assets/fonts/MaterialIcons-Regular.otf'
    if not icons.is_file() or icons.stat().st_size == 0:
        raise RuntimeError('A fonte Material Icons está ausente; cliente não será publicado.')
    redist = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/2022/BuildTools/VC/Redist/MSVC'
    crts = sorted(redist.glob('*/x64/Microsoft.VC143.CRT'))
    if not crts:
        raise RuntimeError('Runtime Visual C++ x64 de distribuição não encontrado.')
    for dll in crts[-1].glob('*.dll'):
        shutil.copy2(dll, staging / dll.name)
    files = {path.relative_to(staging).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(staging.rglob('*')) if path.is_file()}
    manifest = dict(protocol=1, flet='1.0.5', flutter=FLUTTER_VERSION, features=['navigation_v1', 'spatial_camera_v1', 'media_filter_v1'],
        source_fingerprint=source_fingerprint(ROOT), files=files)
    (staging / 'koma-client.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    destination = publish_client(staging)
    print(f'Cliente validado em {destination}', flush=True)


if __name__ == '__main__':
    main()
