"""Uma sessão por documento: salvamento explícito e recuperação independente."""

import json
import os
import shutil
from time import monotonic, time_ns
from pathlib import Path
from uuid import uuid4

from koma.documents.bundle import destination_stamp, export_bundle, restore_bundle, validate_image, thumbnail
from koma.documents.store import StoryboardStore
from koma.editor.models import Storyboard
from koma.paths import atomic_json
from koma.documents.audio import validate_audio


class DocumentSession:
    def __init__(self, data):
        self.data = Path(data)
        self.directory = self.data / 'recovery' / uuid4().hex
        self.directory.mkdir(parents=True)
        self.lease = self._lease(self.directory)
        self.store = StoryboardStore(self.directory)
        self.board = self.saved_board = Storyboard()
        self.path = None
        self.stamp = None
        self.recovered_from = None
        self.recovery_lease = None
        self.backup_at = 0
        self.keep_recovery = False

    @staticmethod
    def _lease(directory):
        """Trava da sessão: outra janela não pode recuperar arquivos em uso."""
        handle = (Path(directory) / '.lock').open('a+b')
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except OSError:
            handle.close()
            raise ValueError('Esta sessão está em uso em outra janela do Koma.')

    @property
    def dirty(self):
        return self.saved_board is None or self.board != self.saved_board

    def recover(self, board, *, backup_interval=0, backup_count=10):
        self.store.save(board)
        if self.saved_board is not None and board == self.saved_board:
            (self.directory / 'session.json').unlink(missing_ok=True)
            return
        atomic_json(self.directory / 'session.json', {
            'version': 1, 'path': str(self.path) if self.path else None,
            'stamp': self.stamp, 'title': board.title,
        })
        if backup_interval and monotonic() - self.backup_at >= backup_interval * 60:
            folder = self.data / 'backups' / self.store.document_id
            folder.mkdir(parents=True, exist_ok=True)
            destination = folder / f'backup-{time_ns()}.koma'
            export_bundle(board, self.store, destination, expected_stamp=None)
            self.backup_at = monotonic()
            for previous in sorted(folder.glob('backup-*.koma'), reverse=True)[backup_count:]:
                previous.unlink(missing_ok=True)

    def save(self, board, destination=None, *, expected_stamp=Ellipsis):
        path = Path(destination).expanduser().resolve().with_suffix('.koma') if destination else self.path
        if path is None:
            raise ValueError('Escolha onde salvar o documento.')
        if expected_stamp is Ellipsis:
            expected_stamp = self.stamp if path == self.path else None
        result = export_bundle(board, self.store, path, expected_stamp=expected_stamp)
        # Atualiza somente depois da publicação bem-sucedida.
        self.path, self.stamp, self.saved_board = result, destination_stamp(result), board
        return result

    @classmethod
    def open(cls, path, data):
        session = cls(data)
        try:
            path = Path(path).expanduser().resolve()
            before = destination_stamp(path)
            session.board = session.saved_board = restore_bundle(path, session.store)
            if destination_stamp(path) != before:
                raise ValueError('O arquivo mudou durante a abertura. Tente novamente.')
            session.path, session.stamp = path, before
            return session
        except Exception:
            session.close()
            raise

    @staticmethod
    def recoveries(data):
        available = []
        for path in (Path(data) / 'recovery').glob('*/session.json'):
            try:
                handle = DocumentSession._lease(path.parent)
                handle.close()
                available.append(path)
            except (OSError, ValueError):
                continue
        return sorted(available, key=lambda p: p.stat().st_mtime_ns, reverse=True)

    @classmethod
    def from_recovery(cls, metadata, data):
        metadata = Path(metadata).resolve()
        root = (Path(data) / 'recovery').resolve()
        if metadata.parent.parent != root or metadata.name != 'session.json':
            raise ValueError('Sessão de recuperação inválida.')
        session = cls(data)
        try:
            raw = json.loads(metadata.read_text(encoding='utf-8'))
            if raw.get('version') != 1:
                raise ValueError('Versão de recuperação inválida.')
            session.recovery_lease = cls._lease(metadata.parent)
            shutil.copytree(metadata.parent, session.directory, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.lock'))
            session.board = session.store.load()
            session.saved_board = None
            session.path = Path(raw['path']) if raw.get('path') else None
            stamp = raw.get('stamp')
            session.stamp = tuple(stamp) if stamp is not None else None
            session.recovered_from = metadata.parent
            for track in session.board.audio_tracks:
                validate_audio(session.store.audio / track.asset, track.duration)
            from koma.documents.media_assets import validate_assets
            from koma.editor.node_media import board_assets
            validate_assets(session.board, session.store)
            for name in {name for kind, name in board_assets(session.board) if kind == 'images'}:
                validate_image(session.store.images / name)
                session.store.thumbnails.mkdir(exist_ok=True)
                thumbnail(session.store.images / name, session.store.thumbnails / name)
            return session
        except Exception:
            session.close()
            raise

    def close(self, *, resolved=False):
        # Só remove diretórios UUID criados dentro da raiz de recuperação.
        root = (self.data / 'recovery').resolve()
        self.lease.close()
        if self.recovery_lease is not None:
            self.recovery_lease.close()
        for directory in (self.directory, self.recovered_from if resolved else None):
            if directory == self.directory and self.keep_recovery:
                continue
            if directory is not None and directory.resolve().parent == root:
                shutil.rmtree(directory, ignore_errors=True)
