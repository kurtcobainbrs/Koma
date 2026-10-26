# Build: python -m PyInstaller --noconfirm Koma.spec
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

root = Path(SPECPATH)
sys.path.insert(0, str(root / 'scripts'))
from koma.ui.drop_runtime import validate_client, development_client
datas = collect_data_files('koma', includes=['assets/**', 'themes/**'])
# É código executado por outro Python (Blender), não um módulo do PYZ.
datas += [(str(root / 'src/koma/exports/blender_probe.py'), 'koma/exports')]
binaries = []
hiddenimports = ['_miniaudio', '_cffi_backend']
for package in ('flet', 'flet_desktop'):
    package_data, package_binaries, package_imports = collect_all(package,
        filter_submodules=lambda name: not name.startswith(('flet.testing', 'flet.security', 'flet.fastapi')))
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += collect_submodules('koma', filter=lambda name: not name.endswith('.blender_probe'))
client = validate_client(development_client(root))
datas += [(str(path), str(Path('desktop/flet') / path.relative_to(client).parent))
          for path in sorted(client.rglob('*')) if path.is_file()]

a = Analysis([str(root / 'scripts' / 'desktop_entry.py')],
    pathex=[str(root / 'src')], binaries=binaries, datas=datas,
    hookspath=[str(root / 'scripts/pyinstaller_hooks')],
    hiddenimports=hiddenimports, excludes=['tkinter', '_tkinter', 'pytest'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Koma',
    debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Koma')
