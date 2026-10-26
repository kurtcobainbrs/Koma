"""Abertura por soltura compartilha o fluxo de abas e preserva a sessão ativa."""

from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from tests import test_project_tabs as fixtures

finish = fixtures.finish


class ProjectDropTests(TestCase):
    setUp = fixtures.ProjectTabsTests.setUp
    cleanup_views = fixtures.ProjectTabsTests.cleanup_views
    second = fixtures.ProjectTabsTests.second

    def event(self, files, **changes):
        values = dict(protocol=1, session_token=self.app.view.session.directory.name, files=[str(path) for path in files])
        values.update(changes)
        return Data(**values)

    def test_valid_project_opens_in_new_tab_preserving_dirty_board_and_history(self):
        with patch('koma.ui.drop_runtime.enabled', return_value=True):
            self.app.surface = self.app.project_drop.surface(self.app.host)
        self.assertTrue(self.app.project_drop.control.documents_only)
        finish(self.view.add_frame())
        self.view.session.save(self.view.board, self.target)
        finish(self.view.add_frame())
        before, history = self.view.board, tuple(self.view.history.past)
        # A soltura na janela usa o mesmo validador de abertura do menu.
        # Como esse caminho já está aberto, seleciona a aba em memória.
        other = self.second()
        with patch('koma.documents.session.DocumentSession.open', side_effect=AssertionError('Não deve reabrir uma aba existente')):
            finish(self.app.project_drop.handle(self.event([self.target])))
        self.assertIs(self.app.view, self.view)
        self.assertEqual(self.view.board, before)
        self.assertFalse(self.app.project_drop.control.disabled)
        self.assertEqual(self.app.project_drop.control.session_token, self.app.view.session.directory.name)
        self.assertEqual(tuple(self.view.history.past), history)
        self.assertTrue(self.view.dirty)
        finish(self.app.select_view(other))
        copy = self.root / 'cópia.KOMA'
        copy.write_bytes(self.target.read_bytes())
        finish(self.app.project_drop.handle(self.event([copy])))
        self.assertEqual(len(self.app.views), 3)
        self.assertEqual(len(self.app.view.board.frames), 1)
        self.assertEqual(self.view.board, before)

    def test_bad_mixed_stale_or_busy_drops_leave_current_project_intact(self):
        finish(self.view.add_frame())
        before = self.view.board
        bad = self.root / 'corrompido.koma'; bad.write_bytes(b'not a project')
        for event in (self.event([bad]), self.event([bad, self.root / 'image.png']),
                self.event([bad], protocol=99), self.event([bad], session_token='another-tab')):
            finish(self.app.project_drop.handle(event))
            self.assertEqual(len(self.app.views), 1)
            self.assertIs(self.view.board, before)
            self.assertFalse(self.view.busy)
        self.view.lock(True)
        finish(self.app.project_drop.handle(self.event([bad])))
        self.assertIs(self.view.board, before)
        self.view.lock(False)

    def test_canvas_compatibility_routes_project_before_image_hit_test(self):
        self.view.session.save(self.view.board, self.target)
        copy = self.root / 'outro.koma'; copy.write_bytes(self.target.read_bytes())
        image_drop = AsyncMock()
        with patch.object(self.view.image_input, 'drop', image_drop):
            finish(self.view.external_drop.handle(self.event([copy])))
        image_drop.assert_not_awaited()
        self.assertEqual(len(self.app.views), 2)
        self.assertEqual(self.app.view.session.path, copy.resolve())
