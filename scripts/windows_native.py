"""Política de DLLs do cliente fixado e auditoria PE do pacote Windows."""

import hashlib
import json
import os
import re
from pathlib import Path

import pefile

FLET_VERSION = '1.0.5'
UNUSED_FLET_DLLS = {
    'dartjni.dll': '1886f3466b794cf04362e38ec542cbc209b1ae7512b0e16db750c59be842e2d7',
    'zlib.dll': '82d5bf175cf882ac9afc1558b416e674606d055966bc09529076b28a498fc0e4',
}
NATIVE_SUFFIXES = {'.dll', '.exe', '.pyd'}
DEBUG_RUNTIME = re.compile(r'(?:vcruntime\d+(?:_\d+)?d|msvcp\d+d|ucrtbased)\.dll$', re.I)
# Só DLLs do Windows padrão. Não aceitar qualquer biblioteca instalada em System32.
WINDOWS_SYSTEM_DLLS = set('''advapi32.dll avicap32.dll avrt.dll bcrypt.dll cfgmgr32.dll
comctl32.dll crypt32.dll d3d11.dll d3d9.dll dbghelp.dll dwmapi.dll dxgi.dll gdi32.dll
gdiplus.dll imm32.dll iphlpapi.dll kernel32.dll mf.dll mfplat.dll mfreadwrite.dll
ntdll.dll ole32.dll oleacc.dll oleaut32.dll opengl32.dll propsys.dll psapi.dll
rpcrt4.dll shell32.dll shlwapi.dll uiautomationcore.dll user32.dll uxtheme.dll
version.dll winmm.dll ws2_32.dll'''.split())


def inspect_pe(path):
    with pefile.PE(str(path), fast_load=True) as pe:
        pe.parse_data_directories(directories=[1, 13])
        imports = sorted({entry.dll.decode('ascii').lower()
            for name in ('DIRECTORY_ENTRY_IMPORT', 'DIRECTORY_ENTRY_DELAY_IMPORT')
            for entry in getattr(pe, name, [])})
        return {'machine': pe.FILE_HEADER.Machine, 'imports': imports}


def flet_datas(client, version, report_path):
    """Exclui só os dois órfãos conhecidos; mudanças no upstream bloqueiam o build."""
    client = Path(client)
    if version != FLET_VERSION:
        raise ValueError('Reavalie a política de DLLs antes de atualizar o cliente Flet.')
    for name, expected in UNUSED_FLET_DLLS.items():
        path = client / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'O binário Flet {name} mudou; reavalie a exclusão.')
    retained = [path for path in sorted(client.rglob('*')) if path.is_file()
                and path.relative_to(client).as_posix().lower() not in UNUSED_FLET_DLLS]
    imports = {}
    for path in retained:
        if path.suffix.lower() in NATIVE_SUFFIXES:
            info = inspect_pe(path)
            imports[path.relative_to(client).as_posix()] = info
            used = set(info['imports']) & UNUSED_FLET_DLLS.keys()
            if used:
                raise ValueError(f'{path.name} depende de {sorted(used)}; exclusão recusada.')
        # Também verifica referências de carga dinâmica e manifestos, além de imports PE.
        data = path.read_bytes().lower()
        for name in UNUSED_FLET_DLLS:
            if name.encode() in data or name.encode('utf-16-le') in data:
                raise ValueError(f'{path.name} referencia {name}; exclusão recusada.')
    report = {'flet_version': version, 'excluded_orphans': UNUSED_FLET_DLLS,
              'retained_native_files': imports,
              'native_assets': json.loads((client / 'data/flutter_assets/NativeAssetsManifest.json').read_text())}
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return [(str(path), str(Path('desktop/flet') / path.relative_to(client).parent)) for path in retained]


def audit_distribution(directory, report_path, system_directory=None):
    directory = Path(directory).resolve()
    internal = directory / '_internal'
    system_directory = Path(system_directory or Path(os.environ['SystemRoot']) / 'System32')
    native_files = [path for path in sorted(directory.rglob('*'))
                    if path.is_file() and path.suffix.lower() in NATIVE_SUFFIXES]
    errors, rows = [], []
    if not native_files:
        errors.append('O diretório não contém binários Windows.')
    for path in native_files:
        relative = path.relative_to(directory).as_posix()
        info = inspect_pe(path)
        if info['machine'] != 0x8664:
            errors.append(f'{relative}: arquitetura diferente de x64')
        if path.name.lower() in UNUSED_FLET_DLLS:
            errors.append(f'{relative}: DLL órfã não deve entrar no pacote')
        # O cliente Flutter é outro processo: não herda a resolução Python de _internal.
        search = [path.parent] if path.is_relative_to(internal / 'desktop/flet') else [path.parent, internal]
        local_names = {p.name.lower() for folder in search if folder.is_dir() for p in folder.iterdir() if p.is_file()}
        resolved = {}
        for name in info['imports']:
            if DEBUG_RUNTIME.fullmatch(name):
                errors.append(f'{relative}: runtime de depuração {name}')
            if name in local_names:
                resolved[name] = 'bundled'
            elif name.startswith(('api-ms-win-', 'ext-ms-win-')):
                resolved[name] = 'windows-api-set'
            elif name in WINDOWS_SYSTEM_DLLS and (system_directory / name).is_file():
                resolved[name] = 'windows-system'
            else:
                errors.append(f'{relative}: dependência ausente {name}')
                resolved[name] = 'missing'
        rows.append({'file': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'machine': info['machine'], 'dependencies': resolved})
    report = {'architecture': 'x64', 'native_files': rows, 'errors': errors}
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    if errors:
        raise ValueError('Auditoria nativa falhou:\n' + '\n'.join(errors))
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path('dist/Koma'))
    parser.add_argument('--report', type=Path, default=Path('build/windows-native-audit.json'))
    args = parser.parse_args()
    report = audit_distribution(args.directory, args.report)
    print(f"Auditoria PE: {len(report['native_files'])} binários x64, sem dependências ausentes ou runtimes debug.")
