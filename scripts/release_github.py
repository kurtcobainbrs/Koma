"""GitHub Releases: autenticação, retomada de anexos e publicação após conferência."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit


def repository_from_remote(url):
    match = re.fullmatch(r'git@github\.com:(.+)', url)
    if match:
        path = match[1]
    else:
        parsed = urlsplit(url)
        if parsed.scheme not in ('https', 'ssh') or parsed.hostname != 'github.com':
            raise ValueError('O remote precisa apontar para um repositório no github.com.')
        path = parsed.path.lstrip('/')
    path = path.removesuffix('.git')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', path, flags=re.ASCII):
        raise ValueError('Endereço do repositório inválido.')
    return path


def find_gh(root, explicit=None):
    candidate = explicit or os.environ.get('KOMA_GH') or shutil.which('gh')
    pointer = Path(root) / 'build/tools/github-cli-path.txt'
    if not candidate and pointer.is_file():
        candidate = pointer.read_text(encoding='utf-8-sig').strip()
    if not candidate or not Path(candidate).is_file():
        raise ValueError('GitHub CLI não encontrado. Instale gh ou informe --gh CAMINHO.')
    return Path(candidate).resolve()


def authenticated_environment(gh, root, repository):
    env = os.environ.copy()
    env.update(GH_PROMPT_DISABLED='1', GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never', GH_DEBUG='')
    if env.get('GH_TOKEN') or env.get('GITHUB_TOKEN'):
        return env
    status = subprocess.run([str(gh), 'auth', 'status', '--hostname', 'github.com'], cwd=root, env=env, capture_output=True)
    if status.returncode == 0:
        return env
    credential = subprocess.run(['git', '-c', 'credential.interactive=never', 'credential', 'fill'],
        input=f'protocol=https\nhost=github.com\npath={repository}.git\n\n',
        cwd=root, env=env, text=True, encoding='utf-8', capture_output=True)
    values = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
    if credential.returncode or not values.get('password'):
        raise ValueError('Autentique o GitHub CLI com gh auth login antes de publicar.')
    env['GH_TOKEN'] = values['password']
    return env


def file_digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def release_assets(directory, version, commit):
    """Confere só os artefatos a publicar, sem executar testes do aplicativo."""
    directory = Path(directory)
    names = {f'Koma-{version}-windows-x64-setup.exe', f'Koma-{version}-windows-x64-portable.zip',
        'RELEASE-NOTES.md', 'SHA256SUMS.txt', 'build-info.json'}
    if not all((directory / name).is_file() for name in names):
        raise ValueError('A release está incompleta.')
    metadata = json.loads((directory / 'build-info.json').read_text(encoding='utf-8'))
    if metadata.get('version') != version or metadata.get('source_git_head') != commit or metadata.get('source_dirty') is not False:
        raise ValueError('Os artefatos não correspondem a um commit limpo desta versão. Não serão publicados.')
    entries = {}
    for line in (directory / 'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        digest, name = line.split('  ', 1)
        if name not in names - {'SHA256SUMS.txt'} or name in entries or not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise ValueError('Manifesto de checksums inválido.')
        entries[name] = digest
    if set(entries) != names - {'SHA256SUMS.txt'}:
        raise ValueError('Checksums incompletos.')
    for name, expected in entries.items():
        if file_digest(directory / name) != expected:
            raise ValueError(f'Arquivo alterado depois do build: {name}')
    return tuple(directory / name for name in sorted(names))


class GitHubRelease:
    def __init__(self, gh, root, repository, env=None):
        self.gh, self.root, self.repository = str(gh), Path(root), repository
        self.env = env if env is not None else authenticated_environment(gh, root, repository)

    def run(self, *arguments, json_result=False, payload=None):
        result = subprocess.run([self.gh, *arguments], cwd=self.root, env=self.env,
            input=json.dumps(payload).encode('utf-8') if payload is not None else None, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip() or 'O GitHub recusou a operação.')
        return json.loads(result.stdout) if json_result else result.stdout.decode('utf-8').strip()

    def api(self, endpoint, *, method='GET', payload=None, paginate=False):
        arguments = ['api', endpoint, '--method', method]
        if payload is not None:
            arguments += ['--input', '-']
        if paginate:
            arguments += ['--paginate', '--slurp']
        return self.run(*arguments, json_result=True, payload=payload)

    def require_access(self):
        data = self.api(f'repos/{self.repository}')
        if not data.get('permissions', {}).get('push'):
            raise ValueError('A conta autenticada não tem permissão para publicar neste repositório.')

    def get_release(self, tag):
        pages = self.api(f'repos/{self.repository}/releases?per_page=100', paginate=True)
        matches = [release for page in pages for release in page if release['tag_name'] == tag]
        if len(matches) > 1:
            raise ValueError('Há mais de uma release com essa tag.')
        return matches[0] if matches else None

    def publish(self, tag, assets, *, prerelease=True):
        current = self.get_release(tag)
        if current is not None and not current['draft']:
            raise ValueError('Essa release já foi publicada e não será sobrescrita.')
        if current is None:
            arguments = ['release', 'create', tag, '--repo', self.repository, '--draft', '--verify-tag',
                '--latest=false', '--title', f'Koma {tag}', '--notes-file', str(next(path for path in assets if path.name == 'RELEASE-NOTES.md'))]
            if prerelease:
                arguments.append('--prerelease')
            self.run(*arguments)
            current = self.get_release(tag)
            if current is None:
                raise RuntimeError('O rascunho não foi localizado após a criação.')
        remote = {asset['name']: asset for asset in current['assets']}
        expected = {path.name for path in assets}
        if set(remote) - expected:
            raise ValueError('O rascunho tem anexos inesperados. Confira-o antes de retomar.')
        for path in assets:
            if path.name in remote:
                self.verify_asset(path, remote[path.name])
            else:
                self.run('release', 'upload', tag, str(path), '--repo', self.repository)
        current = self.get_release(tag)
        remote = {asset['name']: asset for asset in current['assets']}
        if set(remote) != expected:
            raise ValueError('O upload ainda está incompleto. O rascunho foi preservado.')
        for path in assets:
            self.verify_asset(path, remote[path.name])
        notes = next(path for path in assets if path.name == 'RELEASE-NOTES.md').read_text(encoding='utf-8')
        result = self.api(f'repos/{self.repository}/releases/{current["id"]}', method='PATCH',
            payload=dict(draft=False, prerelease=prerelease, body=notes, make_latest='false' if prerelease else 'true'))
        if result['draft'] or result['prerelease'] != prerelease:
            raise RuntimeError('O GitHub não confirmou o estado da publicação.')
        return result['html_url']

    @staticmethod
    def verify_asset(path, asset):
        if asset['size'] != path.stat().st_size or asset.get('digest') != 'sha256:' + file_digest(path):
            raise ValueError(f'O anexo {path.name} difere do arquivo local. O rascunho foi preservado.')
