"""Drawing integration: transactions, serialization, copied layers and export."""
import json
from io import BytesIO
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace as Data

from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from koma.documents.session import DocumentSession
from koma.documents.store import document, parse_document, DOCUMENT_VERSION
from koma.editor.drawing_models import DrawingLayer, DrawingStroke, erase_strokes
from koma.editor.models import Storyboard, StoryFrame
from koma.editor.node_clipboard import NodeClipboard, capture_selection
from koma.editor.view import StoryboardView
from koma.preferences import AppPreferences
from koma.exports.drawings import paint_image, paint_pdf
from koma.editor.drawing_geometry import SHAPE_TOOLS, SELECT, PENCIL, ERASER
from koma.editor.frame_format import FrameFormat
from koma.editor.shortcuts import Action
from koma.editor.media_models import TimelineMarker
from tests.test_workflow_integration import inline, immediate


class DrawingTests(unittest.TestCase):
    @inline
    async def test_tool_switch_and_first_stroke_use_local_real_patches_only(self):
        from flet.controls.base_control import BaseControl
        from flet.controls.object_patch import ObjectPatch, DiffBuilder
        frame = StoryFrame(x=0, y=0, drawing=DrawingLayer((DrawingStroke(((.2, .3), (.5, .6))),)))
        view = await self.view((frame, StoryFrame(x=480, y=0)))
        player, surface = view.player, view.player.drawing_surface
        ObjectPatch.from_diff(None, view.content, BaseControl)
        forbidden = [player.preview.stack, player.strip.track, player.strip.audio_lane.canvas,
            *(card.viewport.stack for card in view.cards.values())]
        original = DiffBuilder._compare_dataclasses
        def compare(instance, parent, path, src, dst, frozen):
            if any(dst is control for control in forbidden):
                raise AssertionError('Drawing start traversed stable preview/timeline/canvas')
            return original(instance, parent, path, src, dst, frozen)
        def update(*roots):
            for root in roots:
                ObjectPatch.from_diff(root, root, BaseControl)
        before, history = view.board, tuple(view.history.past)
        with patch.object(DiffBuilder, '_compare_dataclasses', compare), \
                patch.object(player, 'render', side_effect=AssertionError('Full player render at drawing start')), \
                patch.object(player, 'render_position', side_effect=AssertionError('Unnecessary preview update')):
            view.page.update.side_effect = update
            for tool in (PENCIL, 'rectangle', ERASER, SELECT):
                surface.choose_tool(tool)
                player.drawing.begin((.2, .3), hit_radius=.02)
                self.assertIsNotNone(player.drawing.drag)
                surface.redraw()
                view.page.update.reset_mock()
                player.drawing.move((.2, .3))
                view.page.update.assert_not_called()
                player.drawing.cancel()
                self.assertFalse(player.controls.disabled)
        view.page.update.side_effect = None
        self.assertIs(view.board, before)
        self.assertEqual(tuple(view.history.past), history)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        worker = patch('asyncio.to_thread', side_effect=immediate)
        worker.start()
        self.addCleanup(worker.stop)
        self.sessions = []

    def tearDown(self):
        for session in self.sessions:
            session.close()

    async def view(self, frames):
        session = DocumentSession(self.directory)
        self.sessions.append(session)
        session.board = Storyboard(frames=frames)
        settings = AppPreferences(self.directory)
        preferences = settings.configuration.editable()
        preferences['animatic']['initial_scope'] = 'Primeira cena'
        await settings.configuration.commit(preferences)
        view = StoryboardView(Mock(), session, settings)
        view.page.show_dialog.side_effect = lambda popup: setattr(popup, 'open', True)
        await view.activate()
        view.player.open()
        view.player.strip.resized(Data(width=800))
        view.player.drawing_surface.resized(Data(width=800, height=450))
        return view

    @inline
    async def test_drawing_releases_native_zoom_after_commit_and_silent_cancel(self):
        with patch('koma.ui.drop_runtime.supports', side_effect=lambda feature: feature == 'navigation_v1'):
            view = await self.view((StoryFrame(x=0, y=0),))
        player, editor = view.player, view.player.drawing
        navigation = player.preview_navigation.content
        for tool in (PENCIL, ERASER, 'rectangle'):
            editor.set_tool(tool)
            self.assertIsNotNone(editor.begin((.2, .3)))
            self.assertFalse(navigation.navigation_enabled)
            editor.move((.5, .7))
            await editor.finish()
            self.assertTrue(navigation.navigation_enabled)
            self.assertFalse(player.controls.ignore_interactions)
        self.assertIsNotNone(editor.begin((.2, .3)))
        view.page.update.reset_mock()
        editor.cancel(update=False)
        self.assertTrue(navigation.navigation_enabled)
        self.assertFalse(player.controls.ignore_interactions)
        view.page.update.assert_not_called()

    @inline
    async def test_draw_commit_visibility_undo_and_redo(self):
        frame, other = StoryFrame(x=0, y=0), StoryFrame(x=480, y=0)
        view = await self.view((frame, other))
        editor = view.player.drawing
        editor.set_tool(PENCIL)
        before = view.board
        with patch.object(view.store, 'save', wraps=view.store.save) as saved:
            editor.begin((.2, .3))
            editor.move((.5, .7))
            self.assertIs(view.board, before)
            saved.assert_not_called()
            await editor.finish()
            saved.assert_called_once()
        layer = view.board.frames[0].drawing
        self.assertEqual(layer.strokes[0].points, ((.2, .3), (.5, .7)))
        self.assertEqual(view.board.frames[1], other)
        self.assertEqual(view.cards[frame.id].viewport.drawing.layer, layer)
        self.assertEqual(len(view.history.past), 1)
        await view.player.strip.undo_edit()
        self.assertFalse(view.board.frames[0].drawing.strokes)
        await view.player.strip.redo_edit()
        self.assertEqual(view.board.frames[0].drawing, layer)
        await editor.toggle_visibility()
        self.assertFalse(view.board.frames[0].drawing.visible)
        self.assertEqual(view.board.frames[0].drawing.strokes, layer.strokes)
        await view.player.strip.undo_edit()
        self.assertTrue(view.board.frames[0].drawing.visible)

    @inline
    async def test_layer_survives_bundle_and_copy_between_projects(self):
        layer = DrawingLayer((DrawingStroke(((.1, .2), (.6, .8)), '#123456', .01),))
        view = await self.view((StoryFrame(x=0, y=0, drawing=layer),))
        path = self.directory / 'drawing.koma'
        view.session.save(view.board, path)
        opened = DocumentSession.open(path, self.directory)
        self.sessions.append(opened)
        self.assertEqual(opened.board.frames[0].drawing, layer)
        target = await self.view(())
        payload = await capture_selection(view.board, view.store, {view.board.frames[0].id})
        await NodeClipboard().insert(target, payload)
        self.assertEqual(target.board.frames[0].drawing, layer)
        raw = json.loads(json.dumps(document(view.board, view.store.document_id)))
        self.assertEqual(raw['version'], DOCUMENT_VERSION)
        for version in (1, 2, 3):
            old = dict(raw, version=version, frames=[dict(raw['frames'][0])])
            old['frames'][0].pop('drawing')
            restored, _ = parse_document(old)
            self.assertEqual(restored.frames[0].drawing, DrawingLayer())

    @inline
    async def test_eraser_sweep_cancel_and_single_undo(self):
        stroke = DrawingStroke(((.4, .2), (.4, .8)), '#FF0000', .01)
        frame = StoryFrame(x=0, y=0, drawing=DrawingLayer((stroke,)))
        view = await self.view((frame,))
        editor = view.player.drawing
        editor.set_tool(ERASER)
        editor.begin((.1, .5))
        editor.move((.9, .5))
        self.assertFalse(editor.preview_layer().strokes)
        editor.cancel()
        self.assertEqual(view.board.frames[0].drawing, frame.drawing)
        self.assertFalse(view.history.past)
        editor.begin((.1, .5))
        editor.move((.9, .5))
        await editor.finish()
        self.assertFalse(view.board.frames[0].drawing.strokes)
        self.assertEqual(len(view.history.past), 1)
        await view.player.strip.undo_edit()
        self.assertEqual(view.board.frames[0].drawing, frame.drawing)
        self.assertEqual(erase_strokes((stroke,), (.1, .1), (.2, .1), .01, 9 / 16), (stroke,))

    @inline
    async def test_frame_change_and_escape_discard_unfinished_stroke(self):
        view = await self.view((StoryFrame(x=0, y=0), StoryFrame(x=480, y=0)))
        player, editor = view.player, view.player.drawing
        editor.set_tool(PENCIL)
        editor.begin((.1, .2))
        editor.move((.3, .4))
        await player.key_down(Data(key='Escape'))
        self.assertIsNone(editor.drag)
        self.assertTrue(player.opened)
        self.assertFalse(view.history.past)
        editor.begin((.1, .2))
        player.position = 3
        player.render()
        self.assertIsNone(editor.drag)
        self.assertFalse(player.editing)
        self.assertFalse(any(f.drawing.strokes for f in view.board.frames))

    def test_layer_validation_and_export_visibility(self):
        stroke = DrawingStroke(((.5, .5),), '#FF0000', .05)
        layer = DrawingLayer((stroke,))
        image = Image.new('RGB', (200, 100), 'white')
        paint_image(image, layer)
        self.assertEqual(image.getpixel((100, 50)), (255, 0, 0))
        hidden = Image.new('RGB', (100, 200), 'white')
        paint_image(hidden, replace(layer, visible=False))
        self.assertEqual(hidden.getpixel((50, 100)), (255, 255, 255))
        output = BytesIO()
        canvas = Canvas(output)
        paint_pdf(canvas, layer, 0, 0, 200, 100)
        canvas.save()
        self.assertTrue(output.getvalue().startswith(b'%PDF'))
        for invalid in (DrawingStroke(((float('nan'), .2),)), DrawingStroke(((.1, .2),), 'bad'),
                DrawingStroke(((.1, .2),), width=0)):
            with self.assertRaises(ValueError):
                DrawingLayer((invalid,)).validate()

    @inline
    async def test_color_picker_escape_and_player_close_keep_dialog_order(self):
        view = await self.view((StoryFrame(x=0, y=0),))
        player = view.player
        player.drawing_surface.pick_color()
        self.assertIsNotNone(player.drawing_surface.picker)
        await player.key_down(Data(key='Escape'))
        self.assertIsNone(player.drawing_surface.picker)
        self.assertTrue(player.opened)
        player.drawing_surface.pick_color()
        view.page.pop_dialog.reset_mock()
        player.close()
        self.assertEqual(view.page.pop_dialog.call_count, 1)
        self.assertFalse(player.opened)

    @inline
    async def test_transparent_measured_surface_routes_real_gesture_callbacks(self):
        import flet as ft
        view = await self.view((StoryFrame(x=0, y=0),))
        surface = view.player.drawing_surface
        # A measured Positioned becomes MeasureSize(Positioned(...)) in Flet,
        # violating Flutter's Stack parent-data contract before any input arrives.
        self.assertIsNone(surface.content.on_size_change)
        self.assertIs(surface.content.content, surface.tool_menu.content)
        self.assertIs(surface.tool_menu.content.content, surface.viewport)
        self.assertTrue(all(getattr(surface.viewport, edge) is None for edge in ('left', 'top', 'right', 'bottom')))
        self.assertEqual(surface.content.bgcolor, ft.Colors.TRANSPARENT)
        self.assertEqual(surface.gesture.content.bgcolor, ft.Colors.TRANSPARENT)
        surface.viewport.on_size_change(Data(width=800, height=450))
        surface.choose_tool(PENCIL)
        self.assertFalse(surface.content.ignore_interactions)
        surface.gesture.on_pan_down(Data(local_position=Data(x=80, y=90)))
        surface.gesture.on_pan_start(Data(local_position=Data(x=160, y=180)))
        surface.gesture.on_pan_update(Data(local_position=Data(x=400, y=225)))
        self.assertTrue(surface.overlay.canvas.shapes)
        self.assertEqual((surface.overlay.canvas.width, surface.overlay.canvas.height), (800, 450))
        await surface.gesture.on_pan_end(None)
        stroke = view.board.frames[0].drawing.strokes[0]
        self.assertEqual(stroke.points, ((.1, .2), (.2, .4), (.5, .5)))

    def test_shapes_use_project_geometry_and_existing_stroke_renderers(self):
        for format in (FrameFormat(1920, 1080), FrameFormat(1080, 1920)):
            for tool in SHAPE_TOOLS.values():
                points = tool.points((.2, .2), (.7, .8), format.size, .01)
                layer = DrawingLayer((DrawingStroke(points, '#FF0000', .01),))
                layer.validate()
                if tool.key == 'circle':
                    xs, ys = zip(*points)
                    self.assertAlmostEqual((max(xs) - min(xs)) * format.width,
                        (max(ys) - min(ys)) * format.height, delta=1)
                    self.assertEqual(points[0], points[-1])
                if tool.key == 'rectangle':
                    self.assertEqual(points, ((.2, .2), (.7, .2), (.7, .8), (.2, .8), (.2, .2)))
                image = Image.new('RGB', (200, 100), 'black')
                paint_image(image, layer)
                self.assertIsNotNone(image.getbbox())
                self.assertEqual(tool.points((.5, .5), (.5, .5), format.size, .01), ())

    @inline
    async def test_shape_menu_commits_owned_strokes_with_one_undo_per_shape(self):
        view = await self.view((StoryFrame(x=0, y=0),))
        surface, editor = view.player.drawing_surface, view.player.drawing
        for item, tool in zip(surface.shapes.items, SHAPE_TOOLS.values()):
            await item.on_click(None)
            self.assertEqual(editor.tool, tool.key)
            self.assertFalse(surface.content.ignore_interactions)
            before, history = view.board, len(view.history.past)
            editor.begin((.2, .2))
            editor.move((.7, .8))
            self.assertIs(view.board, before)
            self.assertEqual(len(view.history.past), history)
            await editor.finish()
            self.assertEqual(len(view.history.past), history + 1)
            self.assertEqual(view.board.frames[0].drawing.strokes[-1].points,
                tool.points((.2, .2), (.7, .8), view.board.frame_format.size,
                    editor.width / min(view.board.frame_format.size)))
            self.assertEqual(view.store.load(), view.board)
            await view.player.strip.undo_edit()
            self.assertEqual(view.board, before)
            await view.player.strip.redo_edit()
            self.assertEqual(len(view.board.frames[0].drawing.strokes), history + 1)

    @inline
    async def test_toolbar_tools_and_width_controls_share_one_value(self):
        import flet as ft
        view = await self.view((StoryFrame(x=0, y=0),))
        surface = view.player.drawing_surface
        self.assertTrue(surface.options.visible)
        self.assertEqual(surface.tools.alignment, ft.MainAxisAlignment.START)
        self.assertIs(view.player.drawing_slot.content, surface.tools)
        self.assertEqual(surface.color.bgcolor, view.player.drawing.color)
        surface.width_slider.value = 12
        surface.width_slider.on_change(Data(control=surface.width_slider))
        self.assertEqual(view.player.drawing.width, 12)
        self.assertEqual(surface.width.value, '12')
        self.assertEqual(view.page.update.call_args.args, (surface.width,))
        surface.width.value = '17'
        surface.width.on_submit(None)
        self.assertEqual(view.player.drawing.width, 17)
        self.assertEqual(surface.width_slider.value, 17)
        surface.width.value = '0'
        surface.width.on_blur(None)
        self.assertEqual(surface.width.value, '17')
        self.assertFalse(view.history.past)
        from koma.ui.menus import MENU_HORIZONTAL_PADDING
        expected_width = surface.shapes.width + MENU_HORIZONTAL_PADDING * 2
        self.assertEqual(surface.shapes.size_constraints.min_width, expected_width)
        self.assertEqual(surface.shapes.size_constraints.max_width, expected_width)

    @inline
    async def test_select_and_move_changes_only_the_owned_vector_and_is_undoable(self):
        points = SHAPE_TOOLS['rectangle'].points((.2, .2), (.7, .8), (1920, 1080), .01)
        rectangle = DrawingStroke(points, '#FF0000', .01)
        other = DrawingStroke(((.8, .1), (.9, .2)), '#0000FF', .01)
        frame = StoryFrame(x=0, y=0, drawing=DrawingLayer((rectangle, other)))
        view = await self.view((frame,))
        surface, editor = view.player.drawing_surface, view.player.drawing
        surface.choose_tool(SELECT)
        await surface.gesture.on_tap_up(Data(local_position=Data(x=240, y=135)))
        self.assertEqual(editor.selected_index(), 0)
        self.assertTrue(surface.selection_box.visible)
        self.assertFalse(view.history.past)
        before = view.board
        with patch.object(view.store, 'save', wraps=view.store.save) as saved:
            editor.begin((.3, .3))
            editor.move((.4, .5))
            self.assertIs(view.board, before)
            saved.assert_not_called()
            await editor.finish()
            saved.assert_called_once()
        strokes = view.board.frames[0].drawing.strokes
        for (x, y), (original_x, original_y) in zip(strokes[0].points, points):
            self.assertAlmostEqual(x, original_x + .1)
            self.assertAlmostEqual(y, original_y + .2)
        self.assertIs(strokes[1], other)
        self.assertEqual(view.history.past_labels[-1], 'Mover desenho')
        self.assertEqual(len(view.history.past), 1)
        self.assertEqual(view.store.load(), view.board)
        self.assertEqual(editor.selected_index(), 0)
        await view.player.strip.undo_edit()
        self.assertEqual(view.board, before)
        self.assertFalse(surface.selection_box.visible)
        await view.player.strip.redo_edit()
        self.assertEqual(view.board.frames[0].drawing.strokes, strokes)

    @inline
    async def test_selection_translation_bounds_cancel_and_empty_click_are_transient(self):
        points = SHAPE_TOOLS['rectangle'].points((.2, .2), (.7, .8), (1920, 1080), .01)
        frame = StoryFrame(x=0, y=0, drawing=DrawingLayer((DrawingStroke(points),)))
        view = await self.view((frame, StoryFrame(x=480, y=0)))
        surface, editor = view.player.drawing_surface, view.player.drawing
        surface.choose_tool(SELECT)
        editor.begin((.3, .3))
        editor.move((2, -1))
        moved = editor.preview_layer().strokes[0]
        xs, ys = zip(*moved.points)
        self.assertAlmostEqual(max(xs), 1)
        self.assertAlmostEqual(min(ys), 0)
        self.assertAlmostEqual(max(xs) - min(xs), .5)
        self.assertAlmostEqual(max(ys) - min(ys), .6)
        editor.cancel()
        self.assertEqual(view.board.frames[0], frame)
        self.assertFalse(view.history.past)
        await view.player.key_down(Data(key='Escape'))
        self.assertIsNone(editor.selected_index())
        self.assertTrue(view.player.opened)
        await surface.gesture.on_tap_up(Data(local_position=Data(x=16, y=9)))
        self.assertIsNone(editor.selected_index())
        self.assertFalse(surface.selection_box.visible)
        self.assertFalse(view.history.past)
        editor.begin((.3, .3))
        editor.move((.4, .4))
        view.player.position = 3
        view.player.render()
        self.assertIsNone(editor.selected_index())
        self.assertIsNone(editor.drag)
        self.assertEqual(view.board.frames[0], frame)

    @inline
    async def test_delete_selected_drawing_has_priority_and_preserves_configured_shortcut(self):
        rectangle = DrawingStroke(SHAPE_TOOLS['rectangle'].points((.2, .2), (.7, .8), (1920, 1080), .01))
        other = DrawingStroke(((.8, .1), (.9, .2)))
        view = await self.view((StoryFrame(x=0, y=0, drawing=DrawingLayer((rectangle, other))),))
        player, editor = view.player, view.player.drawing
        self.assertFalse(hasattr(player.drawing_surface, 'toggle'))
        self.assertEqual(editor.tool, SELECT)
        marker = TimelineMarker(position=1)
        view.board = replace(view.board, markers=(marker,))
        player.rebuild_timeline()
        player.render()
        player.marker_editor.selected = marker.id
        editor.begin((.3, .3))
        await editor.finish()
        self.assertEqual(editor.selected_index(), 0)
        before, history = view.board, len(view.history.past)
        self.assertIs(Action.DELETE_MARKER, Action.DELETE_SELECTION)
        view.keymap.configure({Action.DELETE_SELECTION: ['X']})
        await player.key_down(Data(key='Delete'))
        self.assertIs(view.board, before)
        await player.key_down(Data(key='x'))
        self.assertEqual(view.board.frames[0].drawing.strokes, (other,))
        self.assertEqual(view.board.markers, (marker,))
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.history.past_labels[-1], 'Excluir desenho')
        self.assertIsNone(editor.selected_index())
        self.assertEqual(view.store.load(), view.board)
        await player.strip.undo_edit()
        self.assertEqual(view.board, before)
        await player.strip.redo_edit()
        await player.key_down(Data(key='x'))
        self.assertFalse(view.board.markers)
        self.assertEqual(view.board.frames[0].drawing.strokes, (other,))

    @inline
    async def test_delete_ignores_text_editing_and_active_gestures(self):
        stroke = DrawingStroke(((.5, .5),))
        view = await self.view((StoryFrame(x=0, y=0, drawing=DrawingLayer((stroke,))),))
        player, editor = view.player, view.player.drawing
        editor.begin((.5, .5))
        await editor.finish()
        before = view.board
        player.drawing_surface.focus_width()
        await player.key_down(Data(key='Delete'))
        self.assertIs(view.board, before)
        player.drawing_surface.set_width()
        editor.begin((.5, .5))
        editor.move((.6, .6))
        await player.key_down(Data(key='Delete'))
        self.assertIs(view.board, before)
        self.assertIsNotNone(editor.drag)
        editor.cancel()
        editor.clear_selection()
        await player.key_down(Data(key='Delete'))
        self.assertIs(view.board, before)
        self.assertFalse(view.history.past)

    @inline
    async def test_alt_left_drag_erases_with_one_commit_without_changing_active_tool(self):
        first = DrawingStroke(((.3, .2), (.3, .8)))
        second = DrawingStroke(((.7, .2), (.7, .8)))
        view = await self.view((StoryFrame(x=0, y=0, drawing=DrawingLayer((first, second))),))
        player, editor = view.player, view.player.drawing
        surface = player.drawing_surface
        surface.choose_tool('rectangle')
        before = view.board
        start, end = Data(local_position=Data(x=80, y=225)), Data(local_position=Data(x=400, y=225))
        self.assertIsNone(surface.gesture.on_right_pan_start)
        with patch.object(view.store, 'save', wraps=view.store.save) as saved, \
                patch('koma.ui.drawing_surface.pressed_modifiers', return_value={'Alt'}) as modifiers:
            surface.gesture.on_pan_down(start)
            modifiers.return_value = set()
            surface.gesture.on_pan_start(start)
            token = editor.drag
            self.assertEqual(token.tool, ERASER)
            self.assertEqual(editor.tool, 'rectangle')
            surface.gesture.on_pan_update(end)
            self.assertEqual(editor.preview_layer().strokes, (second,))
            self.assertIs(view.board, before)
            saved.assert_not_called()
            await surface.gesture.on_pan_end(end)
            saved.assert_called_once()
        self.assertEqual(view.board.frames[0].drawing.strokes, (second,))
        self.assertEqual(editor.tool, 'rectangle')
        self.assertEqual(len(view.history.past), 1)
        self.assertEqual(view.store.load(), view.board)
        await player.strip.undo_edit()
        self.assertEqual(view.board, before)
        await player.strip.redo_edit()
        self.assertEqual(view.board.frames[0].drawing.strokes, (second,))
        with patch('koma.ui.drawing_surface.pressed_modifiers', return_value={'Alt', 'Shift'}):
            self.assertIsNone(surface.temporary_tool())
        view.keymap.rebind(Action.DRAG_ERASE, ('Ctrl',))
        with patch('koma.ui.drawing_surface.pressed_modifiers', return_value={'Ctrl'}):
            self.assertEqual(surface.temporary_tool(), ERASER)

    @inline
    async def test_alt_click_and_escape_do_not_leave_an_unfinished_eraser(self):
        stroke = DrawingStroke(((.3, .2), (.3, .8)))
        view = await self.view((StoryFrame(x=0, y=0, drawing=DrawingLayer((stroke,))),))
        player, editor = view.player, view.player.drawing
        surface = player.drawing_surface
        surface.choose_tool(PENCIL)
        point = Data(local_position=Data(x=240, y=225))
        before = view.board
        with patch('koma.ui.drawing_surface.pressed_modifiers', return_value={'Alt'}):
            await surface.gesture.on_tap_up(point)
            self.assertIsNone(editor.drag)
            self.assertIs(view.board, before)
            surface.gesture.on_pan_down(point)
            surface.gesture.on_pan_start(point)
            self.assertFalse(editor.preview_layer().strokes)
            await player.key_down(Data(key='Escape'))
            self.assertTrue(player.opened)
            self.assertIsNone(editor.drag)
            self.assertIsNone(surface.primary_input.token)
            await surface.gesture.on_pan_end(point)
            self.assertIs(view.board, before)
            self.assertFalse(view.history.past)

    @inline
    async def test_tab_opens_icon_list_without_moving_toolbar(self):
        view = await self.view((StoryFrame(x=0, y=0),))
        player, surface = view.player, view.player.drawing_surface
        menu = surface.tool_menu
        menu.content.open = AsyncMock()
        before = view.board
        await player.key_down(Data(key='Tab'))
        self.assertTrue(menu.opened)
        self.assertTrue(menu.content.open_at_pointer)
        menu.content.open.assert_awaited_once()
        self.assertIs(player.drawing_slot.content, surface.tools)
        self.assertEqual(len(menu.content.items), len(SHAPE_TOOLS) + 3)
        self.assertTrue(all(not isinstance(item.content, str) and item.tooltip for item in menu.content.items))
        self.assertLess(menu.content.size_constraints.max_width, surface.width.width)
        self.assertIs(view.board, before)
        await player.key_down(Data(key='Escape'))
        self.assertFalse(menu.opened)
        self.assertIs(player.drawing_slot.content, surface.tools)
        self.assertIs(view.board, before)
        self.assertFalse(view.history.past)

    @inline
    async def test_tools_shortcut_is_configurable_and_skips_fields_and_gestures(self):
        view = await self.view((StoryFrame(x=0, y=0),))
        player, surface = view.player, view.player.drawing_surface
        surface.tool_menu.content.open = AsyncMock()
        surface.focus_width()
        await player.key_down(Data(key='Tab'))
        self.assertFalse(surface.tool_menu.opened)
        surface.set_width()
        surface.choose_tool(PENCIL)
        player.drawing.begin((.2, .2))
        await player.key_down(Data(key='Tab'))
        self.assertFalse(surface.tool_menu.opened)
        player.drawing.cancel()
        view.keymap.configure({Action.DRAWING_TOOLS: ['Q']})
        await player.key_down(Data(key='Tab'))
        self.assertFalse(surface.tool_menu.opened)
        await player.key_down(Data(key='q'))
        self.assertTrue(surface.tool_menu.opened)
        eraser = surface.tool_menu.content.items[2]
        await eraser.on_click(None)
        self.assertFalse(surface.tool_menu.opened)
        self.assertEqual(player.drawing.tool, ERASER)
        self.assertIs(player.drawing_slot.content, surface.tools)

    @inline
    async def test_menu_dismiss_and_player_close_preserve_toolbar(self):
        view = await self.view((StoryFrame(x=0, y=0),))
        player, surface = view.player, view.player.drawing_surface
        menu = surface.tool_menu
        menu.content.open = AsyncMock()
        await surface.toggle_tools()
        menu.content.on_dismiss(None)
        self.assertFalse(menu.opened)
        surface.width.value = '19'
        surface.width.on_submit(None)
        self.assertEqual(player.drawing.width, 19)
        await surface.toggle_tools()
        player.close()
        self.assertFalse(menu.opened)
        view.page.update.reset_mock()
        menu.content.on_dismiss(None)
        self.assertIs(player.drawing_slot.content, surface.tools)
        view.page.update.assert_not_called()
