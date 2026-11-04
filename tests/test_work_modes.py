"""Mode transitions, shared inspector/history and bounded playback updates."""
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from tests import test_storyboard as fixtures
from koma.editor.models import Storyboard, StoryFrame, StoryLink


class WorkModeTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_open_dialog_blocks_workspace_shortcuts_until_closed(self):
        import flet as ft
        from koma.ui.keyboard_scope import dialog_owns_keyboard
        from koma.editor.application_commands import dispatch
        view, player = self.editor()
        player.open()
        popup = ft.AlertDialog(open=True)
        view.page._dialogs = Data(controls=[popup])
        app = Data(page=view.page)
        board, history = view.board, tuple(view.history.past)
        with patch.object(player.drawing_surface, 'toggle_tools') as picker:
            for key in ('Tab', 'Space', 'Delete', '1'):
                self.assertTrue(fixtures.finish(dispatch(app, Data(key=key))))
                fixtures.finish(player.key_down(Data(key=key)))
                fixtures.finish(view.workspace.navigation.key_down(Data(key=key)))
            picker.assert_not_called()
        self.assertTrue(player.opened)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), history)
        nested = ft.AlertDialog(open=True)
        view.page._dialogs.controls.append(nested)
        popup.open = False
        self.assertTrue(dialog_owns_keyboard(view.page))
        nested.open = False
        self.assertFalse(dialog_owns_keyboard(view.page))
        view.page._dialogs.controls.append(ft.SnackBar(content=ft.Text('Pronto'), open=True))
        self.assertFalse(dialog_owns_keyboard(view.page))

    def test_escape_does_not_leave_animatic_when_no_modal_gesture_is_active(self):
        view, player = self.editor()
        player.open()
        board, past = view.board, tuple(view.history.past)
        with patch.object(player, 'close', side_effect=AssertionError('Escape changed workspace')):
            fixtures.finish(player.key_down(Data(key='Escape')))
            fixtures.finish(player.key_down(Data(key='Escape')))
        self.assertTrue(player.opened)
        self.assertIs(view.work_modes.active_surface, view.work_modes.animatic)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)

    def test_mode_shortcuts_use_top_row_digits_and_respect_field_focus_and_remapping(self):
        from koma.editor.shortcuts import Action
        view, player = self.editor()
        board, past = view.board, tuple(view.history.past)
        nav = view.workspace.navigation
        self.assertIsNone(view.keymap.resolve('Numpad 2', (), 'canvas'))
        fixtures.finish(nav.key_down(Data(key='2')))
        self.assertTrue(player.opened)
        player.strip.duration_input.focus()
        fixtures.finish(player.key_down(Data(key='3')))
        self.assertFalse(view.references.active)
        player.strip.duration_input.cancel()
        fixtures.finish(player.key_down(Data(key='3')))
        self.assertTrue(view.references.active)
        fixtures.finish(view.references.key_down(Data(key='1')))
        self.assertFalse(view.references.active)
        self.assertFalse(player.opened)
        view.keymap.rebind(Action.MODE_REFS, ('4',))
        self.assertIsNone(view.keymap.resolve('3', (), 'canvas'))
        fixtures.finish(nav.key_down(Data(key='4')))
        self.assertTrue(view.references.active)
        self.assertIn('4', view.chrome.reference_mode.tooltip)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)

    def editor(self):
        view = self.view()
        for _ in range(3):
            fixtures.finish(view.add_frame())
        view.workspace.navigation.apply_selection({view.board.frames[-1].id}, view.board.frames[-1].id)
        return view, view.player

    def test_modes_use_same_document_history_and_stable_controls_without_a_dialog(self):
        view, player = self.editor()
        board, history = view.board, view.history
        canvas_selection = set(view.workspace.navigation.selection.ids)
        camera = (view.workspace.translation_x, view.workspace.translation_y, view.workspace.zoom)
        inspector = view.properties.content
        player.open()
        self.assertIs(view.work_modes.active_surface, view.work_modes.animatic)
        self.assertIn(view.work_modes.animatic, view.work_modes.center.controls)
        self.assertIs(view.work_modes.animatic.content, player.surface)
        self.assertIs(view.properties.content, inspector)
        self.assertTrue(all(frame is board.frames[i] for i, frame in enumerate(player.timeline.frames)))
        view.page.show_dialog.assert_not_called()
        player.select_node(board.frames[1].id, seek=True)
        player.close()
        self.assertIs(view.board, board)
        self.assertIs(view.history, history)
        self.assertEqual(view.workspace.navigation.selection.ids, canvas_selection)
        self.assertEqual((view.workspace.translation_x, view.workspace.translation_y, view.workspace.zoom), camera)
        self.assertIs(view.properties.content, inspector)
        self.assertIs(view.work_modes.active_surface, view.work_modes.canvas)
        self.assertFalse(view.work_modes.animatic.visible)
        view.page.pop_dialog.assert_not_called()

    def test_playhead_changes_preview_without_changing_selected_node_or_inspector(self):
        view, player = self.editor()
        player.open()
        player.strip.resized(Data(width=800))
        second = view.board.frames[1]
        player.strip.blocks[second.id].seek(None)
        self.assertEqual(view.properties.active, second.id)
        self.assertEqual(player.selection.active, second.id)
        view.page.update.reset_mock()
        with patch.object(view.properties, 'sync') as inspector, patch('koma.editor.timeline.ordered') as graph:
            for position in (0, .5, 2.5, 4.5, 5):
                player.position = position
                player.render_position()
            inspector.assert_not_called()
            graph.assert_not_called()
        self.assertEqual(player.selection.active, second.id)
        self.assertEqual(player.current, 2)
        for call in view.page.update.call_args_list:
            self.assertFalse(any(control is view.content or control is view.canvas
                or control is view.properties.content for control in call.args))

    def test_inspector_edits_node_with_shared_history_and_preserves_text_shortcuts(self):
        view, player = self.editor()
        player.open()
        identifier = view.board.frames[1].id
        player.select_node(identifier, seek=True)
        history = len(view.history.past)
        props = view.properties
        props.duration_frames.on_focus(None)
        props.duration_frames.value = '24*3'
        fixtures.finish(props.duration_frames.on_change(Data(control=props.duration_frames)))
        self.assertEqual(view.board.frames[1].duration, 3)
        self.assertIs(player.timeline.frames[1], view.board.frames[1])
        self.assertEqual(props.duration_frames.value, '24*3')
        fixtures.finish(player.key_down(Data(key='z', ctrl=True)))
        self.assertEqual(view.board.frames[1].duration, 3)
        fixtures.finish(props.duration_frames.on_submit(Data(control=props.duration_frames)))
        self.assertEqual(props.duration_frames.value, '72')
        props.duration_frames.on_blur(None)
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(view.board.frames[1].duration, 2)
        self.assertEqual(view.properties.duration_frames.value, '48')
        fixtures.finish(player.strip.redo_edit())
        self.assertEqual(view.board.frames[1].duration, 3)
        self.assertTrue(player.opened)

    def test_panel_resize_and_collapse_do_not_rebuild_preview_or_modify_document(self):
        view, player = self.editor()
        player.open()
        board, history = view.board, len(view.history.past)
        divider = player.layout.splitter
        height = player.layout.timeline.height
        width = view.properties.content.width
        with patch.object(player.preview, 'set_frame') as image, patch.object(player.strip, 'sync') as track:
            divider.begin(Data(global_position=Data(y=200)))
            divider.move(Data(global_position=Data(y=170)))
            divider.end()
            view.properties_splitter.begin(Data(global_position=Data(x=500)))
            view.properties_splitter.move(Data(global_position=Data(x=470)))
            view.properties_splitter.end()
            image.assert_not_called()
            track.assert_not_called()
        self.assertEqual(player.layout.timeline.height, height + 30)
        self.assertEqual(view.properties.content.width, width + 30)
        self.assertTrue(player.preview_slot.expand)
        view.properties.toggle()
        self.assertTrue(view.properties.reopen_rail.visible)
        self.assertFalse(view.properties_splitter.content.visible)
        fixtures.finish(player.key_down(Data(key='n')))
        self.assertTrue(view.properties.content.visible)
        self.assertTrue(player.opened)
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), history)

    def test_tab_suspend_and_resume_preserve_animatic_position_and_panel_sizes(self):
        view, player = self.editor()
        player.open()
        player.select_node(view.board.frames[1].id, seek=True)
        player.layout.timeline.height = 260
        view.properties.content.width = 330
        fixtures.finish(view.deactivate())
        self.assertFalse(player.opened)
        self.assertTrue(player.suspended)
        view.active = True
        fixtures.finish(view.activate())
        self.assertTrue(player.opened)
        self.assertFalse(player.suspended)
        self.assertEqual(player.position, 2)
        self.assertEqual(player.selection.active, view.board.frames[1].id)
        self.assertEqual(player.layout.timeline.height, 260)
        self.assertEqual(view.properties.content.width, 330)
        self.assertIs(view.work_modes.active_surface, view.work_modes.animatic)

    def test_scene_choice_switches_scope_without_touching_nodes_or_history(self):
        view = self.view()
        a, b = StoryFrame(kind='main', title='A', x=0, y=0), StoryFrame(kind='main', title='B', x=0, y=400)
        first, second = StoryFrame(title='Primeiro', x=480, y=0), StoryFrame(title='Segundo', x=480, y=400)
        board = Storyboard(frames=(a, first, b, second), links=(StoryLink(a.id, first.id), StoryLink(b.id, second.id)))
        view.changed(board)
        view.refresh()
        view.workspace.navigation.apply_selection({first.id}, first.id)
        view.player.open()
        snapshot, history = view.board, len(view.history.past)
        view.player.scene_choice.value = b.id
        view.player.scene_choice.on_select(None)
        self.assertEqual(view.player.scene_anchor, b.id)
        self.assertEqual(view.player.selection.active, second.id)
        self.assertEqual(view.properties.active, second.id)
        self.assertEqual(view.player.media.scope, '')
        self.assertEqual(view.player.position, first.duration)
        self.assertIs(view.board, snapshot)
        self.assertEqual(len(view.history.past), history)

    def test_selected_frame_opens_at_its_time_and_takes_priority_over_previous_selection(self):
        view, player = self.editor()
        player.open()
        player.select_node(view.board.frames[0].id)
        player.close()
        selected = view.board.frames[-1]
        view.workspace.navigation.apply_selection({selected.id}, selected.id)
        player.open()
        self.assertEqual(player.selection.active, selected.id)
        self.assertEqual(player.position, player.timeline.starts[-1])
        self.assertEqual(player.current, len(player.timeline.frames) - 1)

    def test_open_without_canvas_selection_uses_first_then_remembered_scene(self):
        view = self.view()
        a, b = StoryFrame(kind='main', title='A', x=0, y=0), StoryFrame(kind='main', title='B', x=0, y=400)
        first, second = StoryFrame(title='Primeiro', x=480, y=0), StoryFrame(title='Segundo', x=480, y=400)
        view.changed(Storyboard(frames=(a, first, b, second),
            links=(StoryLink(a.id, first.id), StoryLink(b.id, second.id))))
        view.refresh()
        view.workspace.navigation.apply_selection(set())
        board, history = view.board, len(view.history.past)
        player = view.player
        player.open()
        self.assertTrue(player.opened)
        self.assertEqual(player.scene_anchor, a.id)
        player.scene_choice.value = b.id
        player.choose_scene()
        previous = player.timeline
        player.position = first.duration + .5
        player.close()
        player.open()
        self.assertIs(player.timeline, previous)
        self.assertEqual(player.scene_anchor, b.id)
        self.assertEqual(player.position, first.duration + .5)
        self.assertFalse(view.workspace.navigation.selection.ids)
        player.close()
        view.workspace.navigation.apply_selection({first.id}, first.id)
        player.open()
        self.assertEqual(player.scene_anchor, a.id)
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), history)

    def test_empty_scene_can_open_and_switch_to_scene_with_frames(self):
        view = self.view()
        empty = StoryFrame(kind='main', x=0, y=0)
        scene, frame = StoryFrame(kind='main', x=0, y=400), StoryFrame(x=480, y=400)
        view.changed(Storyboard(frames=(empty, scene, frame), links=(StoryLink(scene.id, frame.id),)))
        view.refresh()
        view.workspace.navigation.apply_selection(set())
        player = view.player
        player.open()
        self.assertTrue(player.opened)
        self.assertEqual(player.scene_anchor, empty.id)
        self.assertFalse(player.timeline.frames)
        self.assertTrue(player.play.disabled)
        self.assertFalse(player.scene_choice.disabled)
        player.scene_choice.value = scene.id
        player.choose_scene()
        self.assertEqual(player.timeline.frames, (frame,))
        self.assertFalse(player.play.disabled)

    def test_export_options_leave_animatic_mounted(self):
        view, player = self.editor()
        player.open()
        player.position = 1
        view.files.video_from_player()
        self.assertTrue(player.opened)
        self.assertIs(view.work_modes.active_surface, view.work_modes.animatic)
        self.assertEqual(player.position, 1)
        view.page.show_dialog.assert_called_once()
        view.page.pop_dialog.assert_not_called()

    def test_history_removing_selected_node_reconciles_inspector_and_timeline(self):
        view, player = self.editor()
        selected = view.board.frames[-1].id
        player.open()
        self.assertEqual(player.selection.active, selected)
        fixtures.finish(player.strip.undo_edit())
        self.assertNotIn(selected, {frame.id for frame in view.board.frames})
        self.assertEqual(player.selection.active, view.board.frames[0].id)
        self.assertEqual(view.properties.active, player.selection.active)
        self.assertEqual(player.strip.selected, player.selection.active)
        self.assertTrue(player.opened)

    def test_complete_mode_tree_serializes_with_single_ownership_of_inspector_and_tools(self):
        view, player = self.editor()
        player.open()
        encoder = configure_encode_object_for_msgpack(BaseControl)
        patch_, _, _ = ObjectPatch.from_diff(None, view.content, BaseControl)
        packed = msgpack.packb(patch_.to_message(), default=encoder)
        self.assertTrue(packed)
        self.assertIs(player.drawing_slot.content, player.drawing_surface.tools)
        self.assertIn(view.properties.content, view.work_modes.inspector.controls)
        self.assertIs(player.keyboard.content, view.work_modes.editor)
        self.assertTrue(view.work_modes.content.expand)
        self.assertIs(view.work_modes.content.content, player.keyboard)
        self.assertIn(player.layout.timeline, view.work_modes.editor.controls)
        self.assertFalse(player.keyboard.autofocus)
        self.assertTrue(player.preview_slot.expand)
        player.close()
        player.open()
        self.assertIs(player.drawing_slot.content, player.drawing_surface.tools)

    def test_canvas_roundtrip_preserves_animatic_zoom_position_and_inspector_width(self):
        view, player = self.editor()
        player.open()
        player.strip.resized(Data(width=800))
        player.strip.zoom(2)
        scale = player.strip.scale
        player.position = 2.5
        view.properties.content.width = 360
        player.close()
        view.workspace.navigation.apply_selection(set())
        player.open()
        self.assertEqual(player.position, 2.5)
        self.assertIs(player.strip.scale, scale)
        self.assertEqual(view.properties.content.width, 360)
