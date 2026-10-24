import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from koma.app import KomaApplication
from koma.documents.session import DocumentSession


class DocumentActionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.page = Mock()
        self.page.window.destroy = AsyncMock()
        self.app = KomaApplication(self.page, self.root / 'data')
        self.addCleanup(lambda: self.app.view.session.close())
        await self.app.start()
        self.view = self.app.view
        self.target = self.root / 'documento.koma'

    async def add(self):
        await self.view.add_frame()

    def picker(self, destination=None):
        picker = Mock()
        picker.save_file = AsyncMock(return_value=str(destination) if destination else None)
        picker.pick_files = AsyncMock(return_value=[SimpleNamespace(path=str(destination))] if destination else [])
        return patch('koma.editor.file_actions.ft.FilePicker', return_value=picker)

    async def test_edit_recovers_locally_without_marking_document_saved(self):
        await self.add()
        self.assertTrue(self.view.dirty)
        self.assertIsNone(self.view.session.path)
        self.assertTrue((self.view.session.directory / 'session.json').exists())
        self.assertFalse(self.target.exists())

    async def test_save_cancel_keeps_document_unsaved(self):
        await self.add()
        with self.picker():
            self.assertFalse(await self.view.files.save_document())
        self.assertTrue(self.view.dirty)
        self.assertFalse(self.view.busy)

    async def test_save_then_undo_redo_tracks_saved_snapshot(self):
        await self.add()
        with self.picker(self.target):
            self.assertTrue(await self.view.files.save_document())
        self.assertFalse(self.view.dirty)
        self.assertNotIn(' *', self.view.chrome.name.value)
        await self.view.edit_frame(self.view.board.frames[0].id, 'notes', 'Alteração')
        self.assertTrue(self.view.dirty)
        await self.view.graph.undo()
        self.assertFalse(self.view.dirty)
        await self.view.graph.redo()
        self.assertTrue(self.view.dirty)

    async def test_failed_save_preserves_dirty_and_does_not_close_window(self):
        await self.add()
        self.view.files.choose = AsyncMock(return_value='save')
        with self.picker(self.target), patch.object(self.view.session, 'save', side_effect=OSError('disk full')):
            self.assertFalse(await self.app.close())
        self.page.window.destroy.assert_not_awaited()
        self.assertTrue(self.view.dirty)
        self.assertFalse(self.view.closing)
        self.assertFalse(self.view.busy)
        self.assertTrue(self.view.editable())

    async def test_cancel_close_preserves_session_and_history(self):
        await self.add()
        self.view.files.choose = AsyncMock(return_value='cancel')
        self.assertFalse(await self.app.close())
        self.assertTrue(self.view.history.past)
        self.page.window.destroy.assert_not_awaited()

    async def test_discard_close_cleans_recovery_and_destroys_window(self):
        await self.add()
        directory = self.view.session.directory
        self.view.files.choose = AsyncMock(return_value='discard')
        self.assertTrue(await self.app.close())
        self.page.window.destroy.assert_awaited_once()
        self.assertFalse(directory.exists())

    async def test_new_cancel_and_discard_have_distinct_outcomes(self):
        await self.add()
        old = self.view
        old.files.choose = AsyncMock(return_value='cancel')
        await old.files.new_document()
        self.assertIs(self.app.view, old)
        old.files.choose.return_value = 'discard'
        await old.files.new_document()
        self.assertIsNot(self.app.view, old)
        self.assertFalse(self.app.view.board.frames)
        self.assertFalse(self.app.view.history.past)
        self.assertFalse(self.app.view.dirty)
        self.assertTrue(old.closing)

    async def test_invalid_open_preserves_document_and_history_without_prompt(self):
        await self.add()
        before = self.view.board
        self.target.write_bytes(b'corrupt')
        self.view.files.choose = AsyncMock()
        with self.picker(self.target):
            await self.view.files.open_document()
        self.assertEqual(self.app.view.board, before)
        self.view.files.choose.assert_not_awaited()
        self.assertTrue(self.view.history.past)
        self.assertTrue(self.view.editable())

    async def test_open_valid_document_starts_fresh_history(self):
        await self.add()
        with self.picker(self.target):
            await self.view.files.save_document()
        saved = self.view.board
        await self.view.add_frame()
        self.view.files.choose = AsyncMock(return_value='discard')
        with self.picker(self.target):
            await self.view.files.open_document()
        self.assertEqual(self.app.view.board, saved)
        self.assertFalse(self.app.view.history.past)
        self.assertFalse(self.app.view.dirty)

    async def test_switch_publishes_candidate_caption_after_old_gestures_shutdown(self):
        session = DocumentSession(self.root / 'data')
        session.board = replace(session.board, title='Outro documento')
        session.save(session.board, self.target)
        await self.app.switch_session(session)
        self.assertTrue(self.page.title.startswith('Outro documento · documento.koma'))
        self.page.update.assert_called_with()

    async def test_existing_save_as_requires_explicit_replacement(self):
        await self.add()
        self.target.write_bytes(b'previous')
        self.view.files.choose = AsyncMock(return_value='cancel')
        with self.picker(self.target):
            self.assertFalse(await self.view.files.save_as())
        self.assertEqual(self.target.read_bytes(), b'previous')
        self.assertIsNone(self.view.session.path)

    async def test_revision_saved_is_not_a_later_edit(self):
        await self.add()
        board = self.view.board
        entered = asyncio.Event()
        proceed = asyncio.Event()
        original = self.view.session.save
        async def worker(fn, *args, **kwargs):
            if fn == self.view.session.save:
                entered.set()
                await proceed.wait()
            return fn(*args, **kwargs)
        with self.picker(self.target), patch('asyncio.to_thread', side_effect=worker):
            task = asyncio.create_task(self.view.files.save_document())
            await entered.wait()
            self.view.changed(replace(board, title='Edição posterior'))
            proceed.set()
            self.assertTrue(await task)
        self.assertEqual(self.view.session.saved_board, board)
        self.assertTrue(self.view.dirty)

    async def test_guard_dismissal_is_cancel(self):
        task = asyncio.create_task(self.view.files.choose('Título', 'Mensagem', [('save', 'Salvar')]))
        await asyncio.sleep(0)
        popup = self.page.show_dialog.call_args.args[0]
        popup.on_dismiss(None)
        self.assertEqual(await task, 'cancel')
