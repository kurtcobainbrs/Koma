"""Fluxo direto de marcadores: atalhos contextuais e arraste sem gravações parciais."""

from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch

from koma.editor.marker_edit import marker_position
from koma.editor.shortcuts import Action, default_keymap
from koma.editor.timeline import TimeScale
from tests import test_storyboard as fixtures


class MarkerInteractionTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        fixtures.finish(view.add_frame())
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        self.addCleanup(player.audio_transport.close)
        return view, player

    def key(self, player, key, **modifiers):
        fixtures.finish(player.key_down(Data(key=key, **modifiers)))

    def marker(self, player, position=1):
        player.position = position
        self.key(player, 'm')
        return next(marker for marker in player.timeline.markers if marker.position == position)

    def test_marker_names_increment_after_renaming_and_skip_existing_numbers(self):
        view, player = self.editor()
        first = self.marker(player, 0.5)
        second = self.marker(player, 1)
        self.assertEqual((first.title, second.title), ('M1', 'M2'))
        fixtures.finish(player.media.rename_marker(second.id, 'Corte', view.board, view.session))
        third = self.marker(player, 1.5)
        self.assertEqual(third.title, 'M3')
        fixtures.finish(player.media.rename_marker(third.id, 'M10', view.board, view.session))
        self.assertEqual(self.marker(player, 2).title, 'M11')

    def test_m_creates_directly_and_same_position_selects_without_duplicates_or_dialog(self):
        view, player = self.editor()
        calls = view.page.show_dialog.call_count
        marker = self.marker(player)
        history = len(view.history.past)
        self.key(player, 'm')
        self.assertEqual(len(player.timeline.markers), 1)
        self.assertEqual(player.marker_editor.selected, marker.id)
        self.assertEqual(len(view.history.past), history)
        self.assertEqual(view.page.show_dialog.call_count, calls)

    def test_space_toggles_and_m_can_mark_without_stopping_playback(self):
        view, player = self.editor()
        self.key(player, ' ')
        self.assertTrue(player.playing)
        with patch('koma.editor.timeline_media.monotonic', return_value=player.anchor + .75):
            self.key(player, 'm')
        self.assertTrue(player.playing)
        self.assertEqual(player.timeline.markers[0].position, .75)
        self.key(player, ' ')
        self.assertFalse(player.playing)

    def test_drag_changes_only_preview_and_commits_once_with_undo(self):
        view, player = self.editor()
        marker = self.marker(player)
        before = view.board
        history = len(view.history.past)
        stored = view.store.path.read_bytes()
        editor = player.marker_editor
        token = editor.begin(marker.id, 100, TimeScale(100))
        editor.move(token, 190)
        editor.move(token, 195)
        self.assertIs(view.board, before)
        self.assertEqual(view.store.path.read_bytes(), stored)
        self.assertEqual(len(view.history.past), history)
        self.assertEqual(editor.position, 2)
        self.assertEqual(player.position, marker.position)
        fixtures.finish(editor.finish(token))
        self.assertFalse(view.busy)
        self.assertEqual(player.timeline.markers[0].position, 2)
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(player.timeline.markers[0], marker)

    def test_drag_patches_only_marker_and_guide_without_rendering_preview_or_canvas(self):
        from flet.controls.base_control import BaseControl
        from flet.controls.object_patch import ObjectPatch, DiffBuilder
        view, player = self.editor()
        marker = self.marker(player)
        player.position = .25
        player.render_position()
        lane = player.strip.marker_lane
        flag = lane.flags[marker.id]
        before = view.board
        ObjectPatch.from_diff(None, view.content, BaseControl)
        original = DiffBuilder._compare_dataclasses
        forbidden = [player.preview.stack, player.strip.audio_lane.canvas,
            *(card.viewport.stack for card in view.cards.values())]
        def compare(instance, parent, path, src, dst, frozen):
            if any(dst is control for control in forbidden):
                raise AssertionError('Marker drag traversed stable media/canvas')
            return original(instance, parent, path, src, dst, frozen)
        def update(*roots):
            for root in roots:
                ObjectPatch.from_diff(root, root, BaseControl)
        with patch.object(DiffBuilder, '_compare_dataclasses', compare), \
                patch.object(player, 'render', side_effect=AssertionError('Full player render during drag')), \
                patch.object(player.strip, 'sync', side_effect=AssertionError('Full track sync during drag')):
            view.page.update.side_effect = update
            token = player.marker_editor.begin(marker.id, 100, TimeScale(100))
            view.page.update.reset_mock()
            for x in (120, 145, 190, 195, 195):
                player.marker_editor.move(token, x)
            self.assertTrue(view.page.update.called)
            for call in view.page.update.call_args_list:
                self.assertEqual(call.args, (flag.box, flag.guide))
            self.assertEqual(player.position, .25)
            self.assertIs(view.board, before)
            player.marker_editor.cancel()
        view.page.update.side_effect = None
        self.assertFalse(player.controls.disabled)
        self.assertFalse(view.busy)

    def test_release_includes_final_marker_position_without_moving_playhead(self):
        view, player = self.editor()
        marker = self.marker(player)
        flag = player.strip.marker_lane.flags[marker.id]
        position = player.position
        history = len(view.history.past)
        flag.pointer_down(Data(global_position=Data(x=100)))
        flag.begin(Data(global_position=Data(x=100)))
        flag.move(Data(global_position=Data(x=100 + player.strip.scale.pixels(.5))))
        fixtures.finish(flag.finish(Data(global_position=Data(x=100 + player.strip.scale.pixels(1)))))
        self.assertEqual(player.timeline.markers[0].position, 2)
        self.assertEqual(player.position, position)
        self.assertEqual(len(view.history.past), history + 1)
        self.assertFalse(player.controls.disabled)
        self.assertEqual(view.store.load(), view.board)

    def test_escape_cancels_drag_without_closing_preview_or_touching_history(self):
        view, player = self.editor()
        marker = self.marker(player)
        before, position = view.board, player.position
        token = player.marker_editor.begin(marker.id, 100, TimeScale(100))
        player.marker_editor.move(token, 250)
        self.key(player, 'Escape')
        self.assertTrue(player.opened)
        self.assertIs(view.board, before)
        self.assertEqual(player.position, position)
        self.assertFalse(view.busy)
        fixtures.finish(player.marker_editor.finish(token))
        self.assertIs(view.board, before)

    def test_stale_gesture_does_not_modify_replaced_document(self):
        view, player = self.editor()
        marker = self.marker(player)
        token = player.marker_editor.begin(marker.id, 0, TimeScale(100))
        view.board = replace(view.board, title='Outro estado')
        changed = view.board
        player.marker_editor.move(token, 100)
        fixtures.finish(player.marker_editor.finish(token))
        self.assertIs(view.board, changed)
        self.assertFalse(view.busy)
        self.assertIsNone(player.marker_editor.drag)

    def test_snap_is_optional_and_uses_pixel_distance_at_current_zoom(self):
        view, player = self.editor()
        self.assertEqual(marker_position(1.95, player.timeline, 24, TimeScale(100), (2,), 12), 2)
        self.assertEqual(marker_position(1.95, player.timeline, 24, TimeScale(1000), (2,), 12), 47 / 24)
        marker = self.marker(player)
        self.key(player, 's')
        self.assertFalse(player.marker_editor.snap_enabled)
        token = player.marker_editor.begin(marker.id, 0, TimeScale(100))
        player.marker_editor.move(token, 95)
        self.assertEqual(player.marker_editor.position, 47 / 24)
        player.marker_editor.cancel()

    def test_rename_is_inline_delete_is_undoable_and_text_focus_blocks_transport(self):
        view, player = self.editor()
        marker = self.marker(player)
        calls = view.page.show_dialog.call_count
        self.key(player, 'F2')
        lane = player.strip.marker_lane
        self.assertEqual(lane.renaming, marker.id)
        lane.field.value = 'Corte principal'
        self.key(player, 'm')
        self.key(player, ' ')
        self.key(player, 'Delete')
        self.assertFalse(player.playing)
        self.assertEqual(len(player.timeline.markers), 1)
        fixtures.finish(lane.save_name())
        self.assertEqual(player.timeline.markers[0].title, 'Corte principal')
        self.assertIsNone(lane.renaming)
        self.assertFalse(lane.saving)
        self.assertIs(view.focus.target, player.keyboard)
        self.assertEqual(view.page.show_dialog.call_count, calls)
        self.key(player, 'Delete')
        self.assertEqual(player.timeline.markers, ())
        self.key(player, 'z', ctrl=True)
        self.assertEqual(player.timeline.markers[0].title, 'Corte principal')

    def test_buttons_and_shortcuts_visit_cut_and_marker_union_and_arrows_step_one_frame(self):
        view, player = self.editor()
        self.marker(player, 1)
        self.marker(player, 2)
        self.marker(player, 2.5)
        player.position = 0
        for expected in (1, 2, 2.5, 4):
            player.next(None)
            self.assertEqual(player.position, expected)
        self.key(player, 'Arrow Up')
        self.assertEqual(player.position, 2.5)
        self.key(player, 'ArrowLeft', shift=True)
        self.assertEqual(player.position, 2)
        self.key(player, 'Arrow Right')
        self.assertEqual(player.position, 49 / 24)
        self.key(player, 'Home')
        self.assertEqual(player.position, 0)
        self.key(player, 'End')
        self.assertEqual(player.position, 4)

    def test_duration_focus_keeps_m_and_space_as_text_and_close_discards_drag(self):
        view, player = self.editor()
        player.strip.duration_input.focus()
        self.key(player, 'm')
        self.key(player, ' ')
        self.assertFalse(player.playing)
        self.assertEqual(player.timeline.markers, ())
        player.strip.duration_input.cancel()
        marker = self.marker(player)
        before = view.board
        token = player.marker_editor.begin(marker.id, 0, TimeScale(100))
        player.marker_editor.move(token, 100)
        player.close()
        self.assertIs(view.board, before)
        self.assertFalse(view.busy)
        self.assertIsNone(player.marker_editor.drag)


class TimelineShortcutTests(TestCase):
    def test_timeline_context_keeps_canvas_tools_and_allows_independent_remapping(self):
        keymap = default_keymap()
        self.assertEqual(keymap.resolve('m', context='canvas'), Action.MUTE)
        self.assertEqual(keymap.resolve('m', context='timeline'), Action.ADD_MARKER)
        self.assertEqual(keymap.resolve(' ', context='canvas'), Action.TEMP_PAN)
        self.assertEqual(keymap.resolve(' ', context='timeline'), Action.PLAY)
        keymap.rebind(Action.ADD_MARKER, ('Ctrl+M',))
        self.assertIsNone(keymap.resolve('m', context='timeline'))
        self.assertEqual(keymap.resolve('m', {'Ctrl'}, 'timeline'), Action.ADD_MARKER)
        restored = default_keymap()
        restored.restore(keymap.export())
        self.assertEqual(restored.bindings(Action.ADD_MARKER), ('Ctrl+M',))
