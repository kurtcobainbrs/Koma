# Build: python -m PyInstaller --noconfirm Koma.spec
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from flet_desktop import ensure_client_cached
from importlib.metadata import version

root = Path(SPECPATH)
sys.path.insert(0, str(root / 'scripts'))
from windows_native import flet_datas
datas = collect_data_files('koma', includes=['assets/**', 'themes/**'])
# É código executado por outro Python (Blender), não um módulo do PYZ.
datas += [(str(root / 'src/koma/exports/blender_probe.py'), 'koma/exports')]
binaries = []
hiddenimports = []
for package in ('flet', 'flet_desktop'):
    package_data, package_binaries, package_imports = collect_all(package,
        filter_submodules=lambda name: not name.startswith(('flet.testing', 'flet.security', 'flet.fastapi')))
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += collect_submodules('koma', filter=lambda name: not name.endswith('.blender_probe'))
datas += flet_datas(ensure_client_cached() / 'flet', version('flet-desktop'), root / 'build/flet-native-policy.json')

a = Analysis([str(root / 'scripts' / 'desktop_entry.py')],
    pathex=[str(root / 'src')], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, excludes=['tkinter', 'pytest'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Koma',
    debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Koma')
