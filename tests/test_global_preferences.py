"""Global settings integrations: unchanged projects, shared rendering and recovery."""
from dataclasses import replace
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch, Mock
from PIL import Image, ImageChops
from koma.preferences import AppPreferences
from koma.editor.models import StoryFrame
from koma.editor.shortcuts import Action
from koma.editor.timeline import Timeline
from koma.exports.subtitles import render_subtitle
from koma.exports.video_frames import StoryboardFrames
from koma.exports.reference_overlay import reference_values, frame_references, ReferenceOverlay
from koma.ui.preferences_panel import PreferencesPanel
from koma.preference_catalog import CATEGORIES
from tests import test_storyboard as fixtures


class GlobalPreferencesTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_selection_color_updates_selected_controls_without_changing_theme_or_canvas(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        identifier = view.board.frames[0].id
        view.workspace.navigation.select_node(identifier)
        theme, board = view.page.theme, view.board
        values = view.settings.configuration.editable()
        values['appearance']['selection'] = '#FF0000'
        with patch.object(view, 'refresh', side_effect=AssertionError('Full refresh')):
            fixtures.finish(view.settings.configuration.commit(values))
        self.assertIs(view.page.theme, theme)
        self.assertIs(view.board, board)
        self.assertEqual(view.cards[identifier].box.border.top.color, '#FF0000')
        self.assertEqual(view.workspace.box_selection.overlay.border.top.color, '#FF0000')

    def test_apply_preserves_document_history_and_restart_keeps_settings_and_shortcuts(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        before, revision = view.board, view.revision
        history = (view.history.undo_description, view.history.redo_description)
        view.page.width, view.page.height = 1280, 800
        panel = PreferencesPanel(view)
        fixtures.finish(panel.open())
        panel.controls['scene_prefix'].value = 'Scenes_'
        panel.controls['shot_prefix'].value = 'S_'
        panel.select(next(category for category in CATEGORIES if category.key == 'shortcuts'))
        panel.controls[Action.SELECT].value = 'Ctrl+Alt+X'
        fixtures.finish(panel.save())
        self.assertIs(view.board, before)
        self.assertEqual(view.revision, revision)
        self.assertEqual((view.history.undo_description, view.history.redo_description), history)
        self.assertTrue(view.production.code(view.board.frames[0].id).startswith('S_'))
        reopened = AppPreferences(view.settings.directory)
        self.assertEqual(reopened.configuration.values['identity']['shot_prefix'], 'S_')
        self.assertEqual(reopened.shortcuts.bindings(Action.SELECT), ('Ctrl+Alt+X',))
        self.assertEqual(view.store.load(), before)

    def test_preview_and_export_share_style_and_export_snapshot_stays_immutable(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        frame = replace(view.board.frames[0], subtitle='Referência')
        values = view.settings.configuration.editable()
        values['subtitles'].update(color='#FF0000', background='#0000FF', opacity=40,
            position='Em cima', align='Esquerda', size=6)
        values['reference'].update(current_frame=True, color='#00FF00', position='Embaixo', margin=2)
        values['timeline'].update(counter_digits=6, seconds_decimals=1)
        values['identity']['shot_prefix'] = 'S_'
        fixtures.finish(view.settings.configuration.commit(values))
        snapshot = view.settings.configuration.values
        source = StoryboardFrames((frame,), view.store, (320, 180), (1,), preferences=snapshot)
        picture = next(source.pictures(source.size, 24, lambda: False))
        expected = render_subtitle(frame.subtitle, source.size, snapshot['subtitles'])
        from koma.exports.video_export import FrameComposer
        background = FrameComposer(frame, source.size, include_subtitles=False, preferences=snapshot).compose(None)
        background.paste(expected, (0, 0), expected)
        self.assertIsNone(ImageChops.difference(picture, background).getbbox())
        view.player.open()
        fixtures.finish(view.player.subtitles.prepare(frame.subtitle, view.player.subtitles.revision,
            source.size, snapshot))
        with Image.open(BytesIO(view.player.subtitles.image.src)) as preview:
            self.assertIsNone(ImageChops.difference(preview, expected).getbbox())
        reference = frame_references(Timeline(view.board))[0]
        text = reference_values(frame, reference, local_frame=1, count=1, current_frame=1,
            total_frames=1, fps=24, size=source.size, preferences=snapshot)
        self.assertEqual(text['current_frame'], 'Frame: 000001')
        self.assertTrue(text['shot'].startswith('S_'))
        overlay = ReferenceOverlay((64, 256), ('current_frame',), snapshot['reference'])
        self.assertEqual(overlay.config['position'], 'Embaixo')
        overlay.apply(Image.new('RGB', (64, 256)), text)
        values['subtitles']['color'] = '#FFFFFF'
        fixtures.finish(view.settings.configuration.commit(values))
        self.assertEqual(source.preferences['subtitles']['color'], '#FF0000')
        with self.assertRaises(TypeError):
            source.preferences['subtitles']['color'] = '#000000'

    def test_backups_are_openable_rotated_and_existing_recovery_is_preserved(self):
        from koma.documents.session import DocumentSession
        view = self.view()
        fixtures.finish(view.add_frame())
        for index in range(3):
            board = replace(self.session.board, title=f'Backup {index}')
            self.session.backup_at = 0
            self.session.recover(board, backup_interval=1, backup_count=2)
        backups = sorted((self.session.data / 'backups' / self.session.store.document_id).glob('*.koma'))
        self.assertEqual(len(backups), 2)
        restored = DocumentSession.open(backups[-1], self.session.data)
        try:
            self.assertEqual(restored.board.title, 'Backup 2')
        finally:
            restored.close()
        values = view.settings.configuration.editable()
        values['confirmations']['close'] = False
        fixtures.finish(view.settings.configuration.commit(values))
        self.assertTrue(fixtures.finish(view.files.guard_changes()))
        self.assertTrue(self.session.keep_recovery)
        self.session.close(resolved=True)
        self.assertTrue((self.session.directory / 'session.json').exists())

    def test_project_defaults_only_apply_to_new_documents(self):
        from koma.app import KomaApplication
        from koma.documents.session import DocumentSession
        app = KomaApplication(Mock(), self.root / 'app')
        fixtures.finish(app.view.activate())
        existing = app.view.board
        values = app.settings.configuration.editable()
        values['projects'].update(fps=30, width=1080, height=1920)
        fixtures.finish(app.settings.configuration.commit(values))
        session = DocumentSession(app.settings.directory)
        try:
            new = app.make_view(session)
            fixtures.finish(new.activate())
            self.assertIs(app.view.board, existing)
            self.assertEqual(new.board.fps, 30)
            self.assertEqual(new.board.frame_format.size, (1080, 1920))
        finally:
            session.close()
            app.view.session.close()

    def test_file_preferences_do_not_refresh_canvas_and_failed_save_keeps_active_values(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        view.page.width, view.page.height = 1280, 800
        panel = PreferencesPanel(view)
        fixtures.finish(panel.open())
        panel.values['files']['recent'] = 25
        with patch.object(view, 'refresh', side_effect=AssertionError('Unrelated canvas refresh')):
            fixtures.finish(panel.save())
        self.assertEqual(view.settings.configuration.values['files']['recent'], 25)
        previous = view.settings.configuration.values
        panel = PreferencesPanel(view)
        fixtures.finish(panel.open())
        panel.controls['scene_prefix'].value = 'Other_'
        with patch.object(panel.store, 'write', side_effect=OSError('disk')):
            fixtures.finish(panel.save())
        self.assertIs(view.settings.configuration.values, previous)
        self.assertTrue(panel.status.visible)
