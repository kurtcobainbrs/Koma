"""Compact drawing tools and normalized input on the actual preview rectangle."""
import flet as ft
from koma.ui.event_updates import explicit_updates

from koma.ui.color_picker import ColorPicker
from koma.ui.drawing_overlay import DrawingOverlay
from koma.ui.drawing_input import DrawingInput
from koma.ui.components import toggle_icon
from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT, DRAG_INTERVAL_MS, ICON_SIZE, BORDER, MUTED, RADIUS, input_style
from koma.ui.menus import icon_menu, ShortcutToolMenu, MENU_ICON_SIZE
from koma.ui.vector_icons import eraser_icon
from koma.editor.drawing_geometry import PENCIL, ERASER, SELECT, SHAPE_TOOLS
from koma.editor.drawing_models import MIN_BRUSH_WIDTH, MAX_BRUSH_WIDTH
from koma.editor.drawing_hit_test import stroke_bounds

SELECTION_HIT_RADIUS = APP_PADDING * 1.5

SHAPE_ICONS = {
    'rectangle': ft.Icons.RECTANGLE_OUTLINED, 'circle': ft.Icons.CIRCLE_OUTLINED,
    'line': ft.Icons.HORIZONTAL_RULE, 'arrow': ft.Icons.ARROW_FORWARD,
}


class DrawingSurface:
    def __init__(self, player):
        self.player, self.editor = player, player.drawing
        self.bounds = None
        self.focused = False
        self.picker = None
        self.overlay = DrawingOverlay()
        self.selection_box = ft.Container(visible=False, ignore_interactions=True,
            border=ft.Border.all(1, ft.Colors.PRIMARY), border_radius=RADIUS)
        self.primary_input = DrawingInput(self.editor, self.point, self.hit_radius)
        self.secondary_input = DrawingInput(self.editor, self.point, self.hit_radius, tool=ERASER)
        self.inputs = (self.primary_input, self.secondary_input)
        self.gesture = ft.GestureDetector(on_pan_down=self.primary_input.down, on_pan_start=self.primary_input.begin,
            on_pan_update=self.primary_input.move, on_pan_end=self.primary_input.finish, on_pan_cancel=self.primary_input.cancel,
            on_tap_up=self.primary_input.tap, drag_interval=DRAG_INTERVAL_MS, mouse_cursor=ft.MouseCursor.PRECISE,
            on_right_pan_start=self.secondary_input.begin, on_right_pan_update=self.secondary_input.move,
            on_right_pan_end=self.secondary_input.finish,
            content=ft.Container(bgcolor=ft.Colors.TRANSPARENT))
        # Flet's size observer adds a render object outside Positioned. Measure
        # a non-positioned child so Flutter keeps Stack parent data intact.
        self.viewport = ft.Container(on_size_change=self.resized, bgcolor=ft.Colors.TRANSPARENT,
            content=ft.Stack([self.overlay.content, self.selection_box, self.gesture], fit=ft.StackFit.EXPAND,
                clip_behavior=ft.ClipBehavior.HARD_EDGE))
        self.content = ft.Container(left=0, right=0, top=0, bottom=0,
            bgcolor=ft.Colors.TRANSPARENT, content=self.viewport)
        self.select = self.button(ft.Icons.NEAR_ME_OUTLINED, 'Selecionar e mover desenho', lambda e: self.choose_tool(SELECT), toggle=True)
        self.pencil = self.button(ft.Icons.EDIT_OUTLINED, 'Lápis', lambda e: self.choose_tool(PENCIL), toggle=True)
        self.eraser = toggle_icon(eraser_icon(ICON_SIZE, MUTED),
            eraser_icon(ICON_SIZE, ft.Colors.PRIMARY), lambda e: self.choose_tool(ERASER))
        self.eraser.tooltip = 'Borracha · botão direito'
        self.shapes = icon_menu([(shape.key, shape.label, SHAPE_ICONS[shape.key])
            for shape in SHAPE_TOOLS.values()], self.choose_tool,
            icon=ft.Icons.CATEGORY_OUTLINED, tooltip='Formas', icon_size=ICON_SIZE)
        self.color = ft.Container(width=ICON_SIZE, height=ICON_SIZE, bgcolor=self.editor.color,
            border=ft.Border.all(1, BORDER), border_radius=RADIUS,
            tooltip='Cor do desenho', on_click=self.pick_color)
        self.width = ft.TextField(value=str(self.editor.width), width=COMPACT_CONTROL_HEIGHT * 2,
            suffix=ft.Text('px'), tooltip=f'Espessura · {MIN_BRUSH_WIDTH} a {MAX_BRUSH_WIDTH} pixels do projeto',
            on_submit=self.submit_width, on_blur=self.set_width, max_length=len(str(MAX_BRUSH_WIDTH)),
            on_focus=self.focus_width,
            counter=ft.Container(width=0, height=0), **input_style(height=COMPACT_CONTROL_HEIGHT))
        self.width_slider = ft.Slider(min=MIN_BRUSH_WIDTH, max=MAX_BRUSH_WIDTH,
            divisions=MAX_BRUSH_WIDTH - MIN_BRUSH_WIDTH, value=self.editor.width,
            width=COMPACT_CONTROL_HEIGHT * 4, height=COMPACT_CONTROL_HEIGHT, label='{value} px',
            on_change=self.change_width, on_change_end=self.change_width)
        self.visibility = self.button(ft.Icons.LAYERS_OUTLINED, 'Ocultar desenho deste quadro', self.editor.toggle_visibility)
        self.options = ft.Row([self.select, self.pencil, self.eraser, self.shapes, self.color, self.width, self.width_slider],
            tight=True, wrap=True, alignment=ft.MainAxisAlignment.START, spacing=APP_PADDING)
        self.tools = ft.Row([self.options, self.visibility], wrap=True,
            alignment=ft.MainAxisAlignment.START, spacing=APP_PADDING, run_spacing=APP_PADDING)
        choices = [(SELECT, 'Selecionar', ft.Icon(ft.Icons.NEAR_ME_OUTLINED, size=MENU_ICON_SIZE)),
            (PENCIL, 'Lápis', ft.Icon(ft.Icons.EDIT_OUTLINED, size=MENU_ICON_SIZE)),
            (ERASER, 'Borracha', eraser_icon(MENU_ICON_SIZE, MUTED)),
            *[(shape.key, shape.label, ft.Icon(SHAPE_ICONS[shape.key], size=MENU_ICON_SIZE))
                for shape in SHAPE_TOOLS.values()]]
        self.tool_menu = ShortcutToolMenu(player.view.page, self.viewport, choices, self.choose_tool,
            on_closed=lambda: player.focus_timeline() if player.opened else None)
        self.content.content = self.tool_menu.content

    async def toggle_tools(self):
        if self.tool_menu.opened:
            self.tool_menu.close()
        elif self.player.opened and self.player.view.editable() and not self.player.editing:
            self.player.playing = False
            self.player.render()
            await self.tool_menu.show()

    @staticmethod
    def button(icon, tooltip, handler, *, toggle=False):
        if toggle:
            button = toggle_icon(icon, icon, handler)
            button.tooltip = tooltip
            return button
        return ft.IconButton(icon=icon, tooltip=tooltip, on_click=handler, icon_size=ICON_SIZE,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)

    def point(self, e):
        if not self.bounds:
            return None
        width, height = self.bounds
        return max(0, min(1, e.local_position.x / width)), max(0, min(1, e.local_position.y / height))

    def hit_radius(self):
        return SELECTION_HIT_RADIUS / min(self.bounds) if self.bounds else 0

    def reset_inputs(self):
        for pointer in self.inputs:
            pointer.reset()

    def sync_inputs(self):
        for pointer in self.inputs:
            pointer.sync()

    @explicit_updates
    def resized(self, e):
        if not self.player.presenting:
            return
        if e.width > 0 and e.height > 0 and self.bounds != (e.width, e.height):
            cancelled = self.editor.drag is not None and self.bounds != (e.width, e.height)
            if self.bounds and self.bounds != (e.width, e.height):
                self.editor.cancel(update=False)
            self.bounds = e.width, e.height
            self.redraw()
            if cancelled and self.player.opened:
                self.player.render()

    def redraw(self):
        self.sync_inputs()
        if self.bounds:
            self.overlay.sync(self.editor.preview_layer(), *self.bounds)
            self.sync_selection()
            if self.player.opened:
                self.player.view.page.update(self.overlay.canvas, self.selection_box)

    def sync_selection(self):
        stroke = self.editor.selected_stroke()
        self.selection_box.visible = stroke is not None and self.bounds is not None
        if not self.selection_box.visible:
            return
        width, height = self.bounds
        left, top, right, bottom = stroke_bounds(stroke)
        padding = APP_PADDING + stroke.width * min(width, height) / 2
        self.selection_box.left, self.selection_box.top = max(0, left * width - padding), max(0, top * height - padding)
        self.selection_box.width = min(width, right * width + padding) - self.selection_box.left
        self.selection_box.height = min(height, bottom * height + padding) - self.selection_box.top

    def sync(self):
        self.sync_inputs()
        frame = self.editor.active_frame()
        if self.editor.drag and (frame is None or frame.id != self.editor.drag.frame.id):
            self.editor.cancel(update=False)
        locked = not frame or not self.player.view.editable() or self.player.editing
        self.content.ignore_interactions = bool(locked and not self.editor.drag)
        for control in (self.select, self.pencil, self.eraser, self.shapes, self.color, self.width, self.width_slider, self.visibility):
            control.disabled = bool(locked)
        self.select.selected = self.editor.tool == SELECT
        self.pencil.selected = self.editor.tool == PENCIL
        self.eraser.selected = self.editor.tool == ERASER
        shape = SHAPE_TOOLS.get(self.editor.tool)
        self.shapes.icon = SHAPE_ICONS[shape.key] if shape else ft.Icons.CATEGORY_OUTLINED
        self.shapes.tooltip = f'Formas · {shape.label}' if shape else 'Formas'
        self.color.bgcolor = self.editor.color
        shown = frame.drawing.visible if frame else True
        self.visibility.icon = ft.Icons.LAYERS_OUTLINED if shown else ft.Icons.LAYERS_CLEAR_OUTLINED
        self.visibility.tooltip = 'Ocultar desenho deste quadro' if shown else 'Mostrar desenho deste quadro'
        if self.bounds:
            self.overlay.sync(self.editor.preview_layer(), *self.bounds)
        self.sync_selection()
        self.gesture.mouse_cursor = (ft.MouseCursor.MOVE if self.selection_box.visible else ft.MouseCursor.BASIC) if self.select.selected else ft.MouseCursor.PRECISE

    def choose_tool(self, tool):
        if not self.player.opened or not self.player.view.editable() or self.player.editing:
            return
        self.editor.set_tool(tool)
        self.player.pause_for_edit()
        self.player.set_gesture_locked(False)
        self.refresh()
        self.tool_menu.close()
        self.player.focus_timeline()

    def refresh(self):
        """Publish drawing changes without touching images, tracks or the canvas."""
        self.sync()
        if self.player.presenting:
            self.player.view.page.update(self.tools, self.overlay.canvas, self.selection_box, self.gesture)

    def set_width(self, e=None):
        self.focused = False
        try:
            self.editor.set_width(self.width.value or '')
            self.width.error_text = None
        except (TypeError, ValueError, OverflowError):
            pass
        self.width.value = str(self.editor.width)
        self.width_slider.value = self.editor.width
        self.player.view.page.update(self.width, self.width_slider)

    def change_width(self, e):
        self.editor.set_width(e.control.value)
        self.width.value = str(self.editor.width)
        self.player.view.page.update(self.width)

    def focus_width(self, e=None):
        self.focused = True
        self.player.pause_for_edit()
        self.player.set_gesture_locked(False)

    def submit_width(self, e=None):
        self.set_width(e)
        self.player.focus_timeline()

    def pick_color(self, e=None):
        if self.picker is not None:
            return
        def apply(color):
            self.picker = None
            self.editor.color = color
            self.sync()
            self.player.view.page.update(self.tools)
        def cancelled():
            self.picker = None
        self.player.pause_for_edit()
        self.player.set_gesture_locked(False)
        self.picker = ColorPicker(self.player.view.page, 'Cor do lápis', self.editor.color,
            apply, on_cancel=cancelled)
        self.picker.open()

    def close_picker(self):
        picker, self.picker = self.picker, None
        if picker is not None:
            picker.cancel(None)
