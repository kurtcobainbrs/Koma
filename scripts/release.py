"""One command for the existing cached Windows build and GitHub release pipeline."""
import argparse
from pathlib import Path
import subprocess
import sys
import tomllib

from build_installer import build
from release_github import find_gh, GitHubRelease, release_assets, repository_from_remote

ROOT = Path(__file__).resolve().parents[1]


def git(*args, check=True):
    return subprocess.run(['git', *args], cwd=ROOT, check=check, text=True,
        encoding='utf-8', capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--stable', action='store_true')
    parser.add_argument('--full-tests', action='store_true')
    parser.add_argument('--iscc', type=Path, default=ROOT / 'build/tools/inno-6.7.3/ISCC.exe')
    args = parser.parse_args()
    if git('status', '--porcelain').stdout.strip():
        raise ValueError('Registre as alterações em um commit antes de gerar a release.')
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    tag = f'v{version}'
    commit = git('rev-parse', 'HEAD').stdout.strip()
    branch = git('symbolic-ref', '--quiet', '--short', 'HEAD', check=False).stdout.strip()
    existing = git('rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}', check=False)
    if existing.returncode == 0 and existing.stdout.strip() != commit:
        raise ValueError('A tag já aponta para outro commit; incremente a versão.')
    notes = args.notes.resolve()
    if not notes.is_file() or not notes.read_text(encoding='utf-8').strip():
        raise ValueError('Informe notas de release existentes e não vazias.')
    github = None
    if args.publish:
        if not branch:
            raise ValueError('Selecione uma branch antes de publicar.')
        repository = repository_from_remote(git('remote', 'get-url', 'origin').stdout.strip())
        github = GitHubRelease(find_gh(ROOT), ROOT, repository)
        github.require_access()
        current = github.get_release(tag)
        if current is not None and not current['draft']:
            raise ValueError('Essa release já foi publicada; ela não será sobrescrita.')
    directory = ROOT / f'dist/releases/{tag}'
    if not directory.exists():
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            str(ROOT / 'scripts/build_windows.ps1'), '-Python', sys.executable]
        if args.full_tests:
            command.append('-FullTests')
        subprocess.run(command, cwd=ROOT, check=True)
        if git('rev-parse', 'HEAD').stdout.strip() != commit or git('status', '--porcelain').stdout.strip():
            raise ValueError('As fontes mudaram durante o build. Os artefatos não serão publicados.')
        directory = build(ROOT, args.iscc, notes_path=notes, prerelease=not args.stable)
    assets = release_assets(directory, version, commit)
    if args.publish:
        if existing.returncode:
            git('tag', '-a', tag, '-m', f'Koma {tag}')
        git('push', 'origin', f'HEAD:refs/heads/{branch}')
        git('push', 'origin', f'refs/tags/{tag}')
        print(github.publish(tag, assets, prerelease=not args.stable), flush=True)
    else:
        print(directory, flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        message = exc.stderr if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        raise SystemExit(message) from None
