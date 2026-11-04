"""Guide rendering parity and node metadata integrations; no manual UI tests."""
import json
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from PIL import Image
from koma.editor.camera_models import CameraMotion, CAMERA_PRESETS
from koma.editor.guide_geometry import guide_positions, guide_layer, camera_layer
from koma.editor.models import Storyboard, StoryFrame
from koma.documents.store import document, parse_document
from koma.documents.session import DocumentSession
from koma.editor.view import StoryboardView
from koma.editor.node_clipboard import capture_selection, NodeClipboard
from koma.exports.guides import render_guides
from koma.exports.video_export import FrameComposer
from koma.global_preferences import validate_configuration
from koma.preference_catalog import defaults
from tests import test_storyboard as fixtures


class GuidesCameraTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_geometry_validation_normalized_for_all_presets_and_custom_guides(self):
        options = defaults()['guides']
        options.update(preview=True, center=True, grid=True, safe_action=True, safe_title=True,
            vertical='25; 50; 75', horizontal='12,5; 80')
        self.assertEqual(guide_positions(options['horizontal']), (.125, .8))
        guide_layer(options).validate()
        for preset in CAMERA_PRESETS:
            motion = CameraMotion(preset)
            motion.validate()
            camera_layer(motion, options).validate()
        for invalid in ('NaN', '101', '-1', '20;;40', ';'.join(['5'] * 17)):
            with self.assertRaises(ValueError):
                guide_positions(invalid)
        values = defaults()
        values['guides']['vertical'] = '101'
        with self.assertRaises(ValueError):
            validate_configuration(values)

    def test_preview_and_export_share_pixels_and_have_independent_visibility(self):
        options = defaults()['guides']
        options.update(preview=True, export=True, camera_export=True, center=True, safe_action=True)
        motion = CameraMotion('pan_right', 'Acompanhar personagem')
        for size in ((640, 360), (360, 640), (500, 500)):
            preview = render_guides(motion, size, options)
            exported = render_guides(motion, size, options, exporting=True)
            self.assertEqual(preview.tobytes(), exported.tobytes())
            self.assertIsNotNone(preview.getbbox())
        preview_only = dict(options, export=False, camera_export=False)
        self.assertIsNone(render_guides(motion, (640, 360), preview_only, exporting=True).getbbox())
        self.assertIsNotNone(render_guides(motion, (640, 360), preview_only).getbbox())
        values = defaults()
        values['guides'] = options
        frame = StoryFrame(camera=motion)
        base = Image.new('RGB', (640, 360), '#123456')
        output = FrameComposer(frame, base.size, include_subtitles=False, preferences=values).compose(base)
        expected = base.copy()
        layer = render_guides(motion, base.size, options, exporting=True)
        expected.paste(layer, (0, 0), layer)
        self.assertEqual(output.tobytes(), expected.tobytes())

    def test_camera_dialog_confirm_cancel_undo_bundle_and_copy_between_projects(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        identifier = view.board.frames[0].id
        view.workspace.navigation.apply_selection({identifier}, identifier)
        before, count = view.board, len(view.history.past)
        panel = view.properties.camera
        panel.open()
        popup = view.page.show_dialog.call_args.args[0]
        popup.open = True
        preset, note, visible = popup.content.content.controls
        preset.value, note.value = 'zoom_in', 'Entrar no detalhe'
        fixtures.finish(popup.actions[0].on_click(None))
        self.assertIs(view.board, before)
        panel.open()
        popup = view.page.show_dialog.call_args.args[0]
        popup.open = True
        preset, note, visible = popup.content.content.controls
        preset.value, note.value = 'zoom_in', 'Entrar no detalhe'
        fixtures.finish(popup.actions[-1].on_click(None))
        motion = CameraMotion('zoom_in', 'Entrar no detalhe')
        self.assertEqual(view.board.frames[0].camera, motion)
        self.assertEqual(len(view.history.past), count + 1)
        changed = view.board
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.board, changed)
        path = view.session.save(view.board, self.root / 'camera.koma')
        opened = DocumentSession.open(path, self.root / 'data')
        self.addCleanup(opened.close)
        self.assertEqual(opened.board.frames[0].camera, motion)
        target_session = DocumentSession(self.root / 'data')
        self.addCleanup(target_session.close)
        target = StoryboardView(Mock(), target_session, view.settings)
        fixtures.finish(target.activate())
        payload = fixtures.finish(capture_selection(view.board, view.store, {identifier}))
        fixtures.finish(NodeClipboard().insert(target, payload))
        self.assertEqual(target.board.frames[0].camera, motion)
        self.assertEqual(target.store.load(), target.board)

    def test_version_eight_migrates_defaults_and_global_changes_leave_project_intact(self):
        frame = StoryFrame(camera=CameraMotion('tilt_up'))
        raw = json.loads(json.dumps(document(Storyboard(frames=(frame,)), 'a' * 32)))
        from koma.documents.store import DOCUMENT_VERSION
        self.assertEqual(raw['version'], DOCUMENT_VERSION)
        restored, _ = parse_document(raw)
        self.assertEqual(restored.frames[0].camera, frame.camera)
        raw['version'] = 8
        raw['frames'][0].pop('camera')
        restored, _ = parse_document(raw)
        self.assertEqual(restored.frames[0].camera, CameraMotion())
        view = self.view()
        fixtures.finish(view.add_frame())
        view.player.open()
        board, past = view.board, tuple(view.history.past)
        values = view.settings.configuration.editable()
        values['guides'].update(preview=True, thirds=True, vertical='25; 75')
        fixtures.finish(view.settings.configuration.commit(values))
        self.assertTrue(view.player.guides.pending)
        fixtures.finish(view.player.guides.drain())
        self.assertTrue(view.player.guides.content.visible)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)
