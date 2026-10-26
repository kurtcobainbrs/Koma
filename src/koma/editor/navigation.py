"""Ferramentas e atalhos locais do canvas; não captura a digitação dos campos."""

import flet as ft

from koma.ui.design import BORDER, CONTROL_HEIGHT, MUTED, ON_SELECTION, RADIUS, SELECTION, SURFACE
from koma.editor.geometry import ZOOM_STEP
from koma.editor.selection import NodeSelection
from koma.editor.canvas_tools import canvas_tools
from koma.editor.shortcuts import Action
from koma.editor.shortcut_commands import ShortcutCommands
from koma.keymap import key_name
from koma.editor.modifier_state import pressed_modifiers
from koma.ui.typography import TEXT_SMALL


class CanvasNavigation:
    def __init__(self, workspace):
        self.workspace, self.view = workspace, workspace.view
        self.mode = 'select'
        self.temporary_pan = False
        self.selection = NodeSelection()
        self.shift_keys, self.control_keys, self.alt_keys, self.meta_keys = set(), set(), set(), set()
        self.keymap = self.view.keymap
        self.commands = ShortcutCommands(self)
        self.held_key = None
        self.editing_fields = set()
        self.buttons = {}
        self.definitions = {tool.key: tool for tool in canvas_tools(workspace)}
        for tool in self.definitions.values():
            self.buttons[tool.key] = ft.IconButton(icon=tool.icon, tooltip=self.keymap.describe(tool.label, tool.action), icon_size=19,
                width=CONTROL_HEIGHT, height=CONTROL_HEIGHT, on_click=self.choose(tool.key))
        self.focus_button = ft.IconButton(icon=ft.Icons.CENTER_FOCUS_STRONG, icon_size=19,
            tooltip=self.keymap.describe('Enquadrar selecionados', Action.FOCUS), width=CONTROL_HEIGHT, height=CONTROL_HEIGHT,
            disabled=True, on_click=self.focus_selected)
        self.tools = ft.Container(left=10, top=10, padding=4, bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER), border_radius=RADIUS,
            content=ft.Column([*self.buttons.values(), ft.Divider(height=8, color=BORDER),
                self.focus_button], tight=True, spacing=2))
        self.keyboard = ft.KeyboardListener(content=workspace.viewer,
            on_key_down=self.key_down, on_key_up=self.key_up)
        self.selection_count = ft.Text(size=TEXT_SMALL)
        self.selection_bar = ft.Container(left=10, bottom=10, padding=6, bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER), border_radius=RADIUS, visible=False,
            content=ft.Row([self.selection_count,
                ft.IconButton(icon=ft.Icons.CONTENT_COPY, tooltip=self.keymap.describe('Duplicar selecionados', Action.DUPLICATE),
                    width=CONTROL_HEIGHT, height=CONTROL_HEIGHT, on_click=self.duplicate_selected),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip=self.keymap.describe('Excluir selecionados', Action.DELETE),
                    width=CONTROL_HEIGHT, height=CONTROL_HEIGHT, on_click=self.delete_selected)], tight=True, spacing=6))

    @property
    def selected(self):
        return self.selection.active

    @property
    def effective_mode(self):
        return 'pan' if self.temporary_pan else self.mode

    def choose(self, mode):
        def chosen(e):
            self.set_mode(mode)
            self.focus_keyboard()
        return chosen

    def focus_keyboard(self):
        if not self.view.closing:
            self.view.page.run_task(self.keyboard.focus)

    def set_mode(self, mode):
        if mode not in self.buttons or self.view.busy or self.view.closing:
            return
        self.view.properties.end_adjust()
        self.workspace.grab.cancel()
        if self.workspace.drag:
            self.workspace.cancel_drag(self.workspace.drag.identifier)
        for tool in self.definitions.values():
            if tool.cancel:
                tool.cancel()
        self.workspace.cancel_camera_transition()
        self.workspace.links.cancel()
        self.mode = mode
        self.temporary_pan = False
        self.sync()
        self.view.notify(self.definitions[mode].hint)

    def sync(self, update=True):
        mode = self.effective_mode
        tool = self.definitions[mode]
        self.workspace.scene.ignore_interactions = not tool.edit_nodes
        surface = self.workspace.pointer_surface
        surface.on_tap_down = None
        surface.on_secondary_tap_down = tool.secondary or self.workspace.scene_secondary_click
        surface.on_pan_down = tool.press
        surface.on_pan_start = tool.begin
        surface.on_pan_update = tool.update
        surface.on_pan_end = tool.end
        surface.on_pan_cancel = tool.cancel if tool.begin else None
        if self.workspace.grab.active:
            self.workspace.scene.ignore_interactions = True
            surface.on_tap_down = self.workspace.grab.confirm
            surface.on_secondary_tap_down = self.workspace.grab.cancel
            surface.on_pan_down = surface.on_pan_start = surface.on_pan_update = surface.on_pan_end = surface.on_pan_cancel = None
        self.workspace.viewer.pan_enabled = tool.pan and self.workspace.drag is None and not self.workspace.focusing_region
        self.workspace.viewer.scale_enabled = (self.workspace.drag is None and not self.workspace.box_selection.active
            and not self.workspace.box_zoom.active and not self.workspace.links.cut_points and not self.workspace.focusing_region)
        surface.mouse_cursor = ft.MouseCursor.MOVE if self.workspace.grab.active else tool.cursor
        for key, button in self.buttons.items():
            button.style = ft.ButtonStyle(bgcolor=SELECTION if key == mode else None,
                color=ON_SELECTION if key == mode else MUTED)
        self.focus_button.disabled = not self.selection.ids
        if hasattr(self.view, 'chrome'):
            self.view.chrome.sync()
        if update and not self.view.closing:
            self.view.page.update(self.workspace.content, self.tools)
            if hasattr(self.view, 'chrome'):
                self.view.page.update(self.view.chrome.content)

    def apply_selection(self, identifiers, active=None):
        previous, previous_active = set(self.selection.ids), self.selected
        identifiers = set(identifiers) & set(self.view.cards)
        active = active if active in identifiers else previous_active if previous_active in identifiers else next(
            (key for key in reversed(self.workspace.z_order) if key in identifiers), None)
        self.selection.replace(identifiers, active)
        affected = previous ^ self.selection.ids
        if previous_active != self.selected:
            affected |= {previous_active, self.selected}
        for identifier in affected:
            if identifier in self.view.cards:
                self.view.cards[identifier].highlight(identifier in self.selection.ids,
                    is_active=identifier == self.selected)
        self.focus_button.disabled = not self.selection.ids
        self.selection_count.value = f'{len(self.selection.ids)} selecionados'
        self.selection_bar.visible = bool(self.selection.ids)
        self.workspace.links.highlight_path(self.selection.ids)
        if hasattr(self.view, 'properties'):
            self.view.properties.sync()
            if not self.view.closing:
                self.view.page.update(self.view.properties.content)
        if not self.view.closing:
            self.view.page.update(self.focus_button, self.selection_bar)
            if hasattr(self.view, 'chrome'):
                self.view.chrome.sync()
                self.view.page.update(self.view.chrome.content, self.view.chrome.status)

    def reconcile(self):
        self.selection.replace(self.selection.ids & set(self.view.cards))
        self.focus_button.disabled = not self.selection.ids
        self.selection_bar.visible = bool(self.selection.ids)
        self.selection_count.value = f'{len(self.selection.ids)} selecionados'

    def select_node(self, identifier, *, focus=False):
        if self.effective_mode != 'select' or self.view.busy or self.view.closing:
            return
        if identifier is not None and identifier not in self.view.cards:
            return
        identifiers = self.selection.ids if identifier in self.selection.ids else {identifier} if identifier else set()
        self.apply_selection(identifiers, identifier)
        if identifier in self.view.cards:
            self.workspace.raise_node(identifier)
        if focus:
            self.focus_keyboard()

    def node_click(self, identifier):
        if self.effective_mode != 'select' or self.view.busy or self.view.closing:
            return
        if self.modifier(Action.ADD_SELECTION):
            self.apply_selection(self.selection.ids ^ {identifier}, identifier)
            self.focus_keyboard()
        else:
            self.select_node(identifier, focus=True)

    def field_focus(self, identifier, key, focused):
        field = identifier, key
        if focused:
            self.editing_fields.add(field)
            self.select_node(identifier)
        else:
            self.editing_fields.discard(field)

    async def background_click(self, e):
        mode = self.effective_mode
        if mode == 'select':
            if self.workspace.links.pending:
                self.workspace.links.cancel()
                return
            if not self.modifier(Action.ADD_SELECTION) and not self.modifier(Action.SUBTRACT_SELECTION):
                self.select_node(None)
            self.focus_keyboard()
        elif mode == 'zoom':
            await self.workspace.zoom_at_scene(e.local_position, ZOOM_STEP)
            self.focus_keyboard()

    async def secondary_click(self, e):
        if self.effective_mode == 'zoom':
            await self.workspace.zoom_at_scene(e.local_position, 1 / ZOOM_STEP)

    async def focus_selected(self, e=None):
        if self.selection.ids:
            await self.workspace.focus_nodes(self.selection.ids)
            self.focus_keyboard()

    async def duplicate_selected(self, e=None):
        if self.workspace.drag:
            self.workspace.cancel_drag(self.workspace.drag.identifier)
        if self.selection.ids:
            await self.view.duplicate_frames(self.selection.ids)
            self.focus_keyboard()

    def delete_selected(self, e=None):
        if self.workspace.drag:
            self.workspace.cancel_drag(self.workspace.drag.identifier)
        if self.selection.ids:
            self.view.confirm_remove_frames(self.selection.ids)

    @property
    def modifiers(self):
        return {name for name, keys in [('Shift', self.shift_keys), ('Ctrl', self.control_keys),
            ('Alt', self.alt_keys), ('Meta', self.meta_keys)] if keys}

    def modifier(self, action):
        return self.keymap.modifier_active(action, self.modifiers)

    def drag_detach_active(self):
        physical = pressed_modifiers()
        return self.keymap.modifier_active(Action.DETACH,
            self.modifiers if physical is None else physical)

    def reset_keys(self):
        for keys in (self.shift_keys, self.control_keys, self.alt_keys, self.meta_keys):
            keys.clear()
        self.held_key, self.temporary_pan = None, False

    def refresh_shortcuts(self):
        for tool in self.definitions.values():
            self.buttons[tool.key].tooltip = self.keymap.describe(tool.label, tool.action)
        self.focus_button.tooltip = self.keymap.describe('Enquadrar selecionados', Action.FOCUS)
        self.workspace.fit_button.tooltip = self.keymap.describe('Enquadrar tudo', Action.FIT)
        for card in self.view.cards.values():
            card.refresh_shortcuts()

    async def key_down(self, e):
        key = e.key.lower()
        if key.startswith('shift'):
            self.shift_keys.add(key)
        elif key.startswith('control') or key.startswith('ctrl'):
            self.control_keys.add(key)
        elif key.startswith('alt'):
            self.alt_keys.add(key)
        elif key.startswith(('meta', 'super', 'command')):
            self.meta_keys.add(key)
        if self.editing_fields or self.view.busy or self.view.closing:
            return
        context = 'move' if self.workspace.grab.active else 'canvas'
        action = self.keymap.resolve(e.key, self.modifiers, context)
        if not action:
            fallback = self.keymap.resolve(e.key, (), context)
            if fallback in (Action.CANCEL, Action.CONFIRM):
                action = fallback
        if not action:
            return
        if action == Action.TEMP_PAN:
            if not self.workspace.drag and not self.workspace.box_selection.active and not self.workspace.box_zoom.active:
                self.held_key = key_name(e.key)
                self.temporary_pan = True
                self.sync()
        else:
            await self.commands.execute(action)

    def key_up(self, e):
        key = e.key.lower()
        for pressed in (self.shift_keys, self.control_keys, self.alt_keys, self.meta_keys):
            pressed.discard(key)
        if key_name(e.key) == self.held_key:
            self.held_key = None
            self.temporary_pan = False
            self.sync()
