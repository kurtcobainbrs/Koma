# Build: python -m PyInstaller --noconfirm Koma.spec
from pathlib import Path
import sys
import tomllib
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct

root = Path(SPECPATH)
sys.path.insert(0, str(root / 'scripts'))
from koma.ui.drop_runtime import validate_client, development_client
datas = collect_data_files('koma', includes=['assets/**', 'themes/**'])
datas += [(str(root / 'build/release/licenses'), 'licenses')]
binaries = []
hiddenimports = ['_miniaudio', '_cffi_backend']
# The bundled PyInstaller hook for av collects its codecs and av.libs DLLs.
for package in ('flet', 'flet_desktop'):
    package_data, package_binaries, package_imports = collect_all(package,
        filter_submodules=lambda name: not name.startswith(('flet.testing', 'flet.security', 'flet.fastapi')))
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += collect_submodules('koma')
client = validate_client(development_client(root))
datas += [(str(path), str(Path('desktop/flet') / path.relative_to(client).parent))
          for path in sorted(client.rglob('*')) if path.is_file()]

a = Analysis([str(root / 'scripts' / 'desktop_entry.py')],
    pathex=[str(root / 'src')], binaries=binaries, datas=datas,
    hookspath=[str(root / 'scripts/pyinstaller_hooks')],
    hiddenimports=hiddenimports, excludes=['tkinter', '_tkinter', 'pytest'])
pyz = PYZ(a.pure)
app_version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
version_parts = tuple(map(int, app_version.split('.'))) + (0,)
version_info = VSVersionInfo(ffi=FixedFileInfo(filevers=version_parts, prodvers=version_parts,
    mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)), kids=[
    StringFileInfo([StringTable('040904B0', [StringStruct(key, value) for key, value in (
        ('CompanyName', 'Koma'), ('FileDescription', 'Koma'), ('FileVersion', app_version),
        ('InternalName', 'Koma'), ('OriginalFilename', 'Koma.exe'),
        ('ProductName', 'Koma'), ('ProductVersion', app_version))])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Koma',
    debug=False, strip=False, upx=False, console=False,
    icon=str(root / 'src/koma/assets/koma.ico'), version=version_info)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Koma')
