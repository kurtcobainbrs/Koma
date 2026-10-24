import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from koma.documents.bundle import destination_stamp, export_bundle
from koma.documents.images import import_image, load_thumbnails
from koma.documents.session import DocumentSession
from koma.editor.models import Storyboard, StoryFrame, StoryLink, StoryGroup


class DocumentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.session = self.new_session()
        self.source = self.root / 'referência.png'
        Image.new('RGB', (300, 200), 'red').save(self.source)
        name, _ = import_image(self.source, self.session.store)
        main = StoryFrame(kind='main', title='Cena', scene_color='#AABBCC', x=-100, y=25)
        frame = StoryFrame(title='Quadro', image=name, duration=1.25, subtitle='Olá',
            action='Descrição', audio='Diálogo', notes='Notas', image_fit='contain', crop_x=.5, x=480, y=25)
        self.board = Storyboard('Documento', (main, frame), (StoryLink(main.id, frame.id),),
            (StoryGroup(title='Grupo', members=(main.id, frame.id)),))
        self.session.board = self.board
        self.target = self.root / 'documento.koma'

    def new_session(self):
        session = DocumentSession(self.root / 'data')
        self.addCleanup(session.close)
        return session

    def open(self):
        session = DocumentSession.open(self.target, self.root / 'other-data')
        self.addCleanup(session.close)
        return session

    def test_portable_roundtrip_preserves_all_fields_without_original_image(self):
        self.session.save(self.board, self.target)
        self.source.unlink()
        opened = self.open()
        self.assertEqual(opened.board, self.board)
        self.assertFalse(opened.dirty)
        self.assertEqual(opened.store.document_id, self.session.store.document_id)
        with ZipFile(self.target) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json', f'images/{self.board.frames[1].image}'})

    def test_save_as_changes_path_only_after_success(self):
        self.session.save(self.board, self.target)
        before = self.target.read_bytes()
        with patch('koma.documents.bundle.ZipFile', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.session.save(replace(self.board, title='Outro'), self.root / 'outro.koma')
        self.assertEqual(self.session.path, self.target)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(self.session.saved_board, self.board)

    def test_save_detects_external_change_and_preserves_both_states(self):
        self.session.save(self.board, self.target)
        self.target.write_bytes(b'changed externally')
        with self.assertRaises(ValueError):
            self.session.save(replace(self.board, title='Alterado'))
        self.assertEqual(self.target.read_bytes(), b'changed externally')
        self.assertEqual(self.session.saved_board, self.board)

    def test_same_size_same_mtime_change_is_detected(self):
        import os
        self.session.save(self.board, self.target)
        info = self.target.stat()
        data = bytearray(self.target.read_bytes())
        data[0] ^= 1
        self.target.write_bytes(data)
        os.utime(self.target, ns=(info.st_atime_ns, info.st_mtime_ns))
        with self.assertRaises(ValueError):
            self.session.save(self.board)

    def test_failed_publication_preserves_file_and_cleans_temporary(self):
        self.session.save(self.board, self.target)
        before = self.target.read_bytes()
        original = Path.replace
        def failing(path, destination):
            if Path(destination) == self.target:
                raise OSError('file locked')
            return original(path, destination)
        with patch.object(Path, 'replace', failing):
            with self.assertRaises(OSError):
                self.session.save(replace(self.board, title='Novo'))
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse(list(self.root.glob('.*.tmp')))

    def test_success_keeps_previous_complete_document_as_backup(self):
        self.session.save(self.board, self.target)
        before = self.target.read_bytes()
        self.session.save(replace(self.board, title='Revisão'))
        self.assertEqual(self.target.with_suffix('.koma.bak').read_bytes(), before)
        self.assertEqual(self.open().board.title, 'Revisão')

    def test_missing_image_never_replaces_valid_document(self):
        self.session.save(self.board, self.target)
        before = self.target.read_bytes()
        (self.session.store.images / self.board.frames[1].image).unlink()
        with self.assertRaises(ValueError):
            self.session.save(self.board)
        self.assertEqual(self.target.read_bytes(), before)

    def test_invalid_archive_does_not_mutate_active_session(self):
        self.session.recover(self.board)
        before = self.session.store.path.read_bytes()
        self.target.write_bytes(b'broken')
        with self.assertRaises(ValueError):
            self.open()
        self.assertEqual(self.session.board, self.board)
        self.assertEqual(self.session.store.path.read_bytes(), before)

    def test_unexpected_archive_paths_and_missing_images_are_rejected(self):
        self.session.save(self.board, self.target)
        with ZipFile(self.target) as archive:
            manifest = archive.read('manifest.json')
        for name in ('../outside.png', 'images/unexpected.png', None):
            with self.subTest(name=name):
                with ZipFile(self.target, 'w') as archive:
                    archive.writestr('manifest.json', manifest)
                    if name:
                        archive.writestr(name, b'image')
                with self.assertRaises(ValueError):
                    self.open()
        self.assertFalse((self.root / 'outside.png').exists())

    def test_recovery_preserves_unsaved_document_and_regenerates_thumbnails(self):
        self.session.recover(self.board)
        metadata = self.session.directory / 'session.json'
        (self.session.store.thumbnails / self.board.frames[1].image).unlink()
        self.assertEqual(DocumentSession.recoveries(self.root / 'data'), [])
        self.session.lease.close()  # Simula o encerramento do processo sem limpeza.
        restored = DocumentSession.from_recovery(metadata, self.root / 'data')
        self.addCleanup(restored.close)
        self.assertTrue(restored.dirty)
        self.assertIsNone(restored.path)
        self.assertEqual(restored.board, self.board)
        self.assertTrue(load_thumbnails(restored.board, restored.store)[self.board.frames[1].image])

    def test_recovery_after_save_remembers_external_conflict(self):
        self.session.save(self.board, self.target)
        modified = replace(self.board, title='Não salvo')
        self.session.recover(modified)
        self.session.lease.close()
        restored = DocumentSession.from_recovery(self.session.directory / 'session.json', self.root / 'data')
        self.addCleanup(restored.close)
        self.assertEqual(restored.path, self.target)
        self.target.write_bytes(b'external')
        with self.assertRaises(ValueError):
            restored.save(restored.board)

    def test_saved_state_and_undo_do_not_report_false_dirty(self):
        self.session.save(self.board, self.target)
        self.session.board = replace(self.board, title='Editado')
        self.assertTrue(self.session.dirty)
        self.session.board = self.board
        self.assertFalse(self.session.dirty)
        self.session.recover(self.board)
        self.assertFalse((self.session.directory / 'session.json').exists())

    def test_future_format_version_is_rejected(self):
        self.session.save(self.board, self.target)
        with ZipFile(self.target) as archive:
            raw = json.loads(archive.read('manifest.json'))
        raw['version'] = 2
        with ZipFile(self.target, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(raw))
        with self.assertRaises(ValueError):
            self.open()

    def test_cache_is_regenerated_from_owned_image(self):
        name = self.board.frames[1].image
        (self.session.store.thumbnails / name).unlink()
        self.assertTrue(load_thumbnails(self.board, self.session.store)[name])
