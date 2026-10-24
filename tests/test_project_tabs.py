import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from koma.app import KomaApplication
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from koma.documents.session import DocumentSession
from koma.editor.models import StoryLink
from tests import test_document_actions as fixtures
from PIL import Image

async def immediate(function, *args, **kwargs):
    return function(*args, **kwargs)

def finish(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError('Suspensão inesperada no controlador; use o teste de integração assíncrono.')

class ProjectTabsTests(unittest.TestCase):
    picker = fixtures.DocumentActionsTests.picker

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        worker = patch('asyncio.to_thread', side_effect=immediate)
        worker.start()
        self.addCleanup(worker.stop)
        resume = patch('koma.editor.canvas.StoryboardCanvas.resume', new_callable=AsyncMock)
        resume.start()
        self.addCleanup(resume.stop)
        task = patch('koma.editor.file_actions.StoryboardFiles.track_task')
        task.start()
        self.addCleanup(task.stop)
        self.page = Mock()
        self.page.window.destroy = AsyncMock()
        self.app = KomaApplication(self.page, self.root / 'data')
        self.addCleanup(self.cleanup_views)
        finish(self.app.start())
        self.view = self.app.view
        self.target = self.root / 'documento.koma'

    def cleanup_views(self):
        for view in self.app.views:
            view.closing = True
            finish(view.shutdown())
            view.session.close()

    def second(self):
        finish(self.app.new_document())
        return self.app.view

    def test_plus_follows_last_tab_in_the_same_scroll_row(self):
        second = self.second()
        self.assertEqual(self.app.tabs.row.controls,
            [self.app.tabs.targets[self.view], self.app.tabs.targets[second], self.app.tabs.end_target])
        self.assertIs(self.app.tabs.end_target.content, self.app.tabs.add)

    def test_drag_reorders_tabs_without_switching_or_changing_documents(self):
        first = self.view
        finish(first.add_frame())
        before, history = first.board, tuple(first.history.past)
        second = self.second()
        third = self.second()
        self.app.tabs.targets[third].on_accept(SimpleNamespace(src=SimpleNamespace(
            group=self.app.tabs.group, data=first.session.directory.name)))
        self.assertEqual(self.app.views, [second, third, first])
        self.assertIs(self.app.view, third)
        self.assertEqual(first.board, before)
        self.assertEqual(tuple(first.history.past), history)
        self.app.tabs.targets[second].on_accept(SimpleNamespace(src=SimpleNamespace(
            group=self.app.tabs.group, data=first.session.directory.name)))
        self.assertEqual(self.app.views, [first, second, third])

    def test_drop_at_plus_moves_to_end_and_rejects_foreign_or_busy_drags(self):
        first, second = self.view, self.second()
        event = SimpleNamespace(src=SimpleNamespace(group='other', data=first.session.directory.name))
        self.app.tabs.end_target.on_accept(event)
        self.assertEqual(self.app.views, [first, second])
        event.src.group = self.app.tabs.group
        second.lock(True)
        self.app.tabs.end_target.on_accept(event)
        self.assertEqual(self.app.views, [first, second])
        second.lock(False)
        self.app.tabs.end_target.on_accept(event)
        self.assertEqual(self.app.views, [second, first])

    def test_tabs_are_between_menus_and_canvas(self):
        self.assertIs(self.app.host.controls[0], self.app.menu_host)
        self.assertIs(self.app.host.controls[1], self.app.tabs.content)
        self.assertIs(self.app.host.controls[2], self.app.editor_host)
        self.assertIs(self.app.menu_host.content, self.view.chrome.content)
        self.assertNotIn(self.view.chrome.content, self.view.content.controls)
        self.assertFalse(hasattr(self.view.chrome, 'name_box'))
        self.assertEqual(self.page.title, 'Koma App')
        self.assertEqual(self.app.tabs.entries[self.view][1].value, 'Projeto 1')

    def test_selection_history_links_images_and_camera_survive_tab_switch(self):
        first = self.view
        source = self.root / 'imagem.png'
        Image.new('RGB', (80, 60), 'red').save(source)
        finish(first.import_paths([source]))
        finish(first.add_frame())
        a, b = first.board.frames
        finish(first.graph.connect(a.id, b.id))
        first.workspace.navigation.apply_selection({a.id}, a.id)
        first.workspace.initial_view_done = True
        first.workspace.zoom = 0.7
        first.workspace.translation_x, first.workspace.translation_y = (80, 120)
        board, history = (first.board, tuple(first.history.past))
        second = self.second()
        camera = first.workspace.camera_memory.state
        self.assertIsNotNone(camera)
        finish(second.add_frame())
        self.assertEqual(len(second.board.frames), 1)
        self.assertTrue(finish(self.app.select_view(first)))
        self.assertEqual(first.board, board)
        self.assertTrue(first.thumbnails[a.image])
        self.assertFalse(second.thumbnails)
        self.assertEqual(tuple(first.history.past), history)
        self.assertEqual(first.workspace.navigation.selection.ids, {a.id})
        self.assertEqual(first.workspace.camera_memory.state, camera)
        finish(first.graph.undo())
        self.assertFalse(first.board.links)
        self.assertEqual(len(second.board.frames), 1)
        self.assertTrue(finish(self.app.select_view(second)))
        self.assertFalse(second.history.future)
        self.assertFalse(first.active)
        self.assertTrue(second.active)

    def test_dirty_and_rename_update_only_corresponding_bottom_tab(self):
        first = self.view
        finish(first.add_frame())
        second = self.second()
        self.assertEqual(self.app.tabs.entries[first][1].value, 'Projeto 1 *')
        self.assertEqual(self.app.tabs.entries[second][1].value, 'Projeto 2')
        second.title.value = 'Estudo de câmera'
        finish(second.edit_title(None))
        self.assertEqual(self.app.tabs.entries[second][1].value, 'Estudo de câmera *')
        self.assertEqual(self.app.tabs.entries[first][1].value, 'Projeto 1 *')
        self.assertEqual(self.page.title, 'Koma App')

    def test_cancel_closing_inactive_dirty_tab_preserves_both_projects(self):
        first = self.view
        finish(first.add_frame())
        second = self.second()
        first.files.choose = AsyncMock(return_value='cancel')
        self.assertFalse(finish(self.app.close_tab(first)))
        self.assertIs(self.app.view, second)
        self.assertEqual(len(self.app.views), 2)
        self.assertTrue(first.session.directory.exists())
        self.assertFalse(first.closing)
        self.assertTrue(first.dirty)

    def test_discard_inactive_tab_cleans_only_its_session(self):
        first = self.view
        finish(first.add_frame())
        second = self.second()
        first.files.choose = AsyncMock(return_value='discard')
        self.assertTrue(finish(self.app.close_tab(first)))
        self.assertIs(self.app.view, second)
        self.assertFalse(first.session.directory.exists())
        self.assertTrue(second.session.directory.exists())
        self.assertEqual(self.app.views, [second])
        self.assertNotIn(first.shortcuts_changed, first.keymap.listeners)

    def test_closing_active_tab_selects_neighbor_with_original_state(self):
        first = self.view
        finish(first.add_frame())
        before = first.board
        second = self.second()
        self.assertTrue(finish(self.app.close_tab(second)))
        self.assertIs(self.app.view, first)
        self.assertEqual(first.board, before)
        self.assertTrue(first.active)
        self.assertFalse(first.closing)

    def test_last_closed_tab_leaves_new_clean_project(self):
        old = self.view
        self.assertTrue(finish(self.app.close_tab(old)))
        self.assertEqual(len(self.app.views), 1)
        self.assertIsNot(self.app.view, old)
        self.assertTrue(self.app.view.loaded)
        self.assertFalse(self.app.view.dirty)

    def test_cancel_second_close_prompt_keeps_all_sessions_and_histories(self):
        first = self.view
        finish(first.add_frame())
        second = self.second()
        finish(second.add_frame())
        first.files.choose = AsyncMock(return_value='discard')
        second.files.choose = AsyncMock(return_value='cancel')
        self.assertFalse(finish(self.app.close()))
        self.page.window.destroy.assert_not_awaited()
        for view in (first, second):
            self.assertTrue(view.session.directory.exists())
            self.assertTrue(view.history.past)
            self.assertFalse(view.closing)
            self.assertFalse(view.busy)
        self.assertIs(self.app.view, second)

    def test_failed_save_while_closing_tab_keeps_it_open(self):
        first = self.view
        finish(first.add_frame())
        self.second()
        first.files.choose = AsyncMock(return_value='save')
        first.files._save_document = AsyncMock(side_effect=OSError('disk full'))
        self.assertFalse(finish(self.app.close_tab(first)))
        self.assertIn(first, self.app.views)
        self.assertTrue(first.dirty)
        self.assertFalse(first.closing)
        self.assertFalse(first.busy)

    def test_open_file_already_in_another_tab_selects_it_without_losing_edits(self):
        first = self.view
        finish(first.add_frame())
        with self.picker(self.target):
            finish(first.files.save_document())
        finish(first.add_frame())
        before = first.board
        second = self.second()
        with self.picker(self.target):
            finish(second.files.open_document())
        self.assertIs(self.app.view, first)
        self.assertEqual(len(self.app.views), 2)
        self.assertEqual(first.board, before)
        self.assertTrue(first.dirty)

    def test_save_as_cannot_overwrite_file_open_in_another_tab(self):
        first = self.view
        finish(first.add_frame())
        with self.picker(self.target):
            finish(first.files.save_document())
        before = self.target.read_bytes()
        second = self.second()
        finish(second.add_frame())
        second.files.choose = AsyncMock(return_value='replace')
        with self.picker(self.target):
            self.assertFalse(finish(second.files.save_as()))
        self.assertEqual(self.target.read_bytes(), before)
        self.assertIsNone(second.session.path)
        self.assertTrue(second.dirty)

    def test_busy_operation_blocks_tab_switch_and_close(self):
        first = self.view
        second = self.second()
        second.lock(True)
        self.assertTrue(self.app.tabs.content.disabled)
        self.assertFalse(finish(self.app.select_view(first)))
        self.assertFalse(finish(self.app.close_tab(first)))
        self.assertFalse(finish(self.app.close()))
        second.lock(False)
        self.assertFalse(self.app.tabs.content.disabled)

    def test_tab_controls_stay_mutable_after_serialization_and_switch(self):
        encoder = configure_encode_object_for_msgpack(BaseControl)

        def publish():
            delta, _, _ = ObjectPatch.from_diff(None, self.app.host, BaseControl)
            msgpack.packb(delta.to_message(), default=encoder)
        publish()
        first = self.view
        second = self.second()
        finish(second.add_frame())
        publish()
        finish(self.app.select_view(first))
        finish(first.add_frame())
        publish()
        second.files.choose = AsyncMock(return_value='discard')
        finish(self.app.close_tab(second))
        publish()

    def test_window_close_resolves_every_project(self):
        first = self.view
        finish(first.add_frame())
        second = self.second()
        finish(second.add_frame())
        for view in (first, second):
            view.files.choose = AsyncMock(return_value='discard')
        self.assertTrue(finish(self.app.close()))
        self.page.window.destroy.assert_awaited_once()
        for view in (first, second):
            self.assertTrue(view.closing)
            self.assertFalse(view.session.directory.exists())
