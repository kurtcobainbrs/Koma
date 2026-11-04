"""Per-stroke transactions; no UI controls or file I/O during pointer movement."""
from dataclasses import dataclass, replace
import math

from koma.editor.drawing_models import DrawingLayer, DrawingStroke, MAX_STROKES, MAX_STROKE_POINTS, MAX_LAYER_POINTS, erase_strokes
from koma.editor.drawing_models import MIN_BRUSH_WIDTH, MAX_BRUSH_WIDTH, DEFAULT_BRUSH_WIDTH
from koma.editor.drawing_geometry import PENCIL, ERASER, SELECT, SHAPE_TOOLS, drawing_tool
from koma.editor.drawing_hit_test import select_stroke, translate_stroke


@dataclass
class DrawingDrag:
    board: object
    session: object
    frame: object
    tool: str
    color: str
    width: float
    points: list
    strokes: tuple
    selection_index: int | None = None
    remaining_points: int = MAX_LAYER_POINTS
    last_point: tuple | None = None


class FrameDrawingEditor:
    def __init__(self, player):
        self.player = player
        self.tool = player.view.settings.last_tool if player.view.settings.configuration.values['drawing']['remember'] else SELECT
        self.color = '#FF5252'
        self.width = DEFAULT_BRUSH_WIDTH
        self.drag = None
        self.committing = False
        self.selected = None
        self.selection_owner = None

    def active_frame(self):
        player = self.player
        return player.timeline.frames[player.current] if player.timeline and 0 <= player.current < len(player.timeline.frames) else None

    def set_tool(self, tool):
        self.tool = drawing_tool(tool)
        if tool != SELECT:
            self.clear_selection()

    def clear_selection(self):
        selected = self.selected
        self.selected = self.selection_owner = None
        return selected is not None

    def selected_index(self):
        frame = self.active_frame()
        owner = self.selection_owner
        if (frame is None or owner is None or owner[0] is not self.player.view.session
                or owner[1] != frame.id or owner[2] is not frame.drawing):
            self.clear_selection()
        if self.tool != SELECT or not frame or not frame.drawing.visible:
            return None
        return self.selected

    def selected_stroke(self):
        index = self.selected_index()
        if index is None:
            return None
        layer = self.preview_layer()
        return layer.strokes[index] if index < len(layer.strokes) else None

    def set_width(self, value):
        number = int(value)
        if number != float(value) or not MIN_BRUSH_WIDTH <= number <= MAX_BRUSH_WIDTH:
            raise ValueError('Espessura fora do intervalo permitido.')
        self.width = number

    def begin(self, point, *, hit_radius=0, tool=None):
        player, view = self.player, self.player.view
        tool = drawing_tool(self.tool if tool is None else tool)
        frame = self.active_frame()
        if not frame or not player.opened or not view.editable() or player.editing:
            return
        player.edit_selection.claim(self)
        view.properties.release_field_focus()
        if not frame.drawing.visible:
            view.notify('Mostre a camada de desenho antes de editar.', 'info')
            return
        point_count = sum(len(s.points) for s in frame.drawing.strokes) if tool not in (ERASER, SELECT) else 0
        if tool not in (ERASER, SELECT) and (len(frame.drawing.strokes) >= MAX_STROKES
                or point_count >= MAX_LAYER_POINTS):
            view.notify('A camada atingiu seu limite. Apague traços antes de continuar.', 'warning')
            return
        player.pause_for_edit()
        index = None
        if tool == SELECT:
            self.selected = select_stroke(frame.drawing.strokes, point, hit_radius, view.board.frame_format.aspect_ratio)
            self.selection_owner = (view.session, frame.id, frame.drawing)
            index = self.selected
            if index is None:
                player.set_gesture_locked(False)
                player.drawing_surface.refresh()
                return
        else:
            self.clear_selection()
        width = view.settings.configuration.values['drawing']['eraser'] if tool == ERASER else self.width
        normalized_width = width / min(view.board.frame_format.size)
        self.drag = DrawingDrag(view.board, view.session, frame, tool, self.color,
            normalized_width, [point], frame.drawing.strokes, index,
            MAX_LAYER_POINTS - point_count, point if tool != ERASER else None)
        if tool == ERASER:
            self.move(point)
        player.set_gesture_locked(True)
        player.drawing_surface.refresh()
        player.focus_timeline()
        return self.drag

    def move(self, point):
        drag = self.drag
        if drag is None:
            return
        if point == drag.last_point:
            return
        view = self.player.view
        if view.board is not drag.board or view.session is not drag.session:
            self.cancel()
            return
        if drag.tool == ERASER:
            drag.strokes = erase_strokes(drag.strokes, drag.points[-1], point,
                drag.width / 2, drag.board.frame_format.aspect_ratio)
            drag.points[:] = [point]
        elif drag.tool == SELECT:
            index = drag.selection_index
            moved = translate_stroke(drag.frame.drawing.strokes[index],
                point[0] - drag.points[0][0], point[1] - drag.points[0][1])
            drag.strokes = tuple(moved if i == index else stroke
                for i, stroke in enumerate(drag.frame.drawing.strokes))
        elif drag.tool in SHAPE_TOOLS:
            drag.points[:] = [drag.points[0], point]
        else:
            previous = drag.points[-1]
            format = drag.board.frame_format
            distance = math.hypot((point[0] - previous[0]) * format.width, (point[1] - previous[1]) * format.height)
            if distance < .5 or len(drag.points) >= min(MAX_STROKE_POINTS, drag.remaining_points):
                return
            drag.points.append(point)
        drag.last_point = point
        self.player.drawing_surface.redraw()

    def preview_layer(self):
        if self.drag is None:
            frame = self.active_frame()
            return frame.drawing if frame else DrawingLayer()
        drag = self.drag
        strokes = drag.strokes
        if drag.tool not in (ERASER, SELECT):
            points = (SHAPE_TOOLS[drag.tool].points(drag.points[0], drag.points[-1],
                drag.board.frame_format.size, drag.width) if drag.tool in SHAPE_TOOLS else tuple(drag.points))
            if points:
                strokes += (DrawingStroke(points, drag.color, drag.width),)
        return replace(drag.frame.drawing, strokes=strokes)

    async def finish(self):
        drag = self.drag
        if drag is None:
            return
        layer = self.preview_layer()
        self.drag = None
        view = self.player.view
        if view.board is not drag.board or view.session is not drag.session or not view.editable() or not self.player.opened:
            self.drag = drag
            self.cancel()
            return
        await self.commit_layer(drag.frame, layer, label='Mover desenho' if drag.tool == SELECT else None,
            selection_index=drag.selection_index if drag.tool == SELECT else None)

    async def commit_layer(self, frame, layer, *, label=None, selection_index=None):
        """All layer commands share validation, persistence and timeline refresh."""
        view = self.player.view
        self.player.playing = False
        self.committing = True
        try:
            layer.validate()
            if layer != frame.drawing:
                await view.set_frame_properties(frame.id, drawing=layer, label=label)
            current = next((f for f in view.board.frames if f.id == frame.id), None)
            self.clear_selection()
            if selection_index is not None and current:
                self.selected = selection_index
                self.selection_owner = (view.session, current.id, current.drawing)
        except ValueError as exc:
            view.notify(str(exc), 'warning')
        finally:
            self.committing = False
            self.player.controls.disabled = False
            if self.player.opened:
                self.player.rebuild_timeline()
                self.player.render()
                self.player.focus_timeline()

    def cancel(self, *, update=True):
        if self.drag is None:
            return
        self.drag = None
        self.player.controls.disabled = False
        if update and self.player.opened:
            self.player.set_gesture_locked(False)
            self.player.drawing_surface.refresh()

    async def delete_selected(self):
        player, view = self.player, self.player.view
        index = self.selected_index()
        frame = self.active_frame()
        if index is None or frame is None or not player.opened or not view.editable() or player.editing:
            return False
        layer = replace(frame.drawing, strokes=tuple(stroke for i, stroke in enumerate(frame.drawing.strokes)
            if i != index))
        await self.commit_layer(frame, layer, label='Excluir desenho')
        return True

    async def toggle_visibility(self, e=None):
        frame = self.active_frame()
        if frame and self.player.view.editable() and not self.player.editing:
            await self.commit_layer(frame, replace(frame.drawing, visible=not frame.drawing.visible))
