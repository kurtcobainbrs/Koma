"""Free image workspace; controls cache presentations, never authoritative image data."""
from dataclasses import replace
import asyncio
import math
import flet as ft
from koma.ui.event_updates import explicit_updates
from koma.ui.retained_container import RetainedStack, retain_children
from koma.ui.design import COMPACT_CONTROL_HEIGHT, DRAG_INTERVAL_MS, BORDER, APP_PADDING
from koma.ui.drop_controls import ImageDropScene, ImageDropSurface
from koma.ui import drop_runtime
from koma.editor.reference_actions import ReferenceActions
from koma.editor.reference_models import MAX_REFERENCE_POSITION, REFERENCE_GAP
from koma.editor.selection import NodeSelection, rectangle, intersects
from koma.editor.shortcuts import Action
from koma.editor.reference_geometry import ReferenceExtent
from koma.preview_cache import PREVIEW_SIDES
from koma.ui.viewer_camera import apply_viewer_camera
from koma.editor.reference_transform import AlignmentIndex, bounds, scale_selection
from koma.ui.reference_overlays import ReferenceOverlays
from koma.ui.spatial_view import SpatialView
from koma.ui.canvas_gestures import NativeSecondaryPan
from koma.editor.reference_transform_mode import ReferenceTransformMode


class ReferenceCanvas:
    def __init__(self, view):
        self.view = view
        self.active = self.loading = False
        self.selection = NodeSelection()
        self.cards, self.images, self.models = {}, {}, {}
        self.gesture = None
        self.box_pointer = None
        self.object_pointer = None
        self.extent = ReferenceExtent()
        self.zoom = self.gesture_zoom = 1
        self.translation = (-self.extent.x, -self.extent.y)
        self.viewport = (1000, 600)
        self.pointer = None
        self.pan_mode = False
        self.temporary_pan = None
        self.camera_revision = 0
        self.camera_used = False
        self.camera_task = None
        self.camera_applying = False
        self.layout_ready = asyncio.Event()
        self.modifiers = set()
        self.grid_enabled = False
        self.grid_snap = False
        self.smart_align = True
        self.options = {}
        self.options_key = None
        self.actions = ReferenceActions(self)
        self.transform_mode = ReferenceTransformMode(self)
        self.background = ft.GestureDetector(on_tap_down=self.clear, on_hover=self.hover,
            hover_interval=DRAG_INTERVAL_MS, on_pan_down=self.box_press, on_pan_start=self.box_begin,
            on_pan_update=self.box_move, on_pan_end=self.box_end, on_pan_cancel=self.cancel,
            drag_interval=DRAG_INTERVAL_MS, content=ft.Container(bgcolor=ft.Colors.TRANSPARENT))
        self.box = ft.Container(visible=False, ignore_interactions=True)
        self.overlays = ReferenceOverlays(self)
        self.selection_border = ft.Container(left=0, right=0, top=0, bottom=0, ignore_interactions=True)
        self.selection_handle = ft.GestureDetector(on_pan_start=lambda e: self.begin(None, e, resize=True),
            on_pan_down=lambda e: self.object_press(None, e, resize=True),
            on_pan_update=self.move, on_pan_end=self.finish, on_pan_cancel=self.cancel,
            drag_interval=DRAG_INTERVAL_MS, mouse_cursor=ft.MouseCursor.RESIZE_UP_LEFT_DOWN_RIGHT,
            content=ft.Icon(ft.Icons.OPEN_IN_FULL, size=14))
        self.selection_frame = ft.Stack(visible=False, controls=[
            self.selection_border,
            ft.Container(right=0, bottom=0, width=20, height=20, content=self.selection_handle)])
        self.scene = RetainedStack(hold_updates=lambda: False,
            controls=[self.background, self.box], width=self.extent.width, height=self.extent.height,
            clip_behavior=ft.ClipBehavior.NONE)
        scene = ImageDropScene(content=self.scene) if drop_runtime.enabled() else self.scene
        self.interaction = ft.Container(content=scene, ignore_interactions=False)
        self.viewer = SpatialView(content=self.interaction, expand=True,
            camera_x=self.translation[0], camera_y=self.translation[1],
            on_pose=self.camera_pose, on_camera_start=self.camera_begin,
            on_size_change=self.resized) if drop_runtime.supports('spatial_camera_v1') else ft.InteractiveViewer(content=self.interaction, constrained=False, expand=True,
            pan_enabled=False,
            on_size_change=self.resized,
            alignment=ft.Alignment.TOP_LEFT, boundary_margin=MAX_REFERENCE_POSITION,
            interaction_update_interval=DRAG_INTERVAL_MS,
            on_interaction_start=self.camera_begin, on_interaction_update=self.camera_move)
        self.secondary_pan = NativeSecondaryPan(content=self.viewer, expand=True,
            pan_enabled=False, on_navigation=self.secondary_navigation) if drop_runtime.enabled() else None
        navigation = self.secondary_pan or self.viewer
        self.drop = ImageDropSurface(content=navigation, expand=True,
            on_dropped=self.dropped) if drop_runtime.enabled() else None
        self.modal_capture = ft.GestureDetector(visible=False,
            on_hover=self.transform_mode.hover, hover_interval=DRAG_INTERVAL_MS,
            on_pan_update=self.transform_mode.hover, drag_interval=DRAG_INTERVAL_MS,
            on_tap_down=self.transform_mode.confirm, on_secondary_tap_down=self.cancel,
            content=ft.Container(bgcolor=ft.Colors.TRANSPARENT))
        self.pointer_observer = ft.GestureDetector(content=self.drop or navigation,
            on_hover=self.transform_mode.hover, hover_interval=DRAG_INTERVAL_MS)
        self.keyboard = ft.KeyboardListener(content=ft.Stack([self.pointer_observer, self.modal_capture],
            expand=True, fit=ft.StackFit.EXPAND),
            on_key_down=self.key_down, on_key_up=self.key_up)
        self.body = ft.Container(content=self.keyboard, expand=True)
        self.select_button = self.button(ft.Icons.NEAR_ME_OUTLINED, 'Selecionar', lambda e: self.set_pan(False))
        self.pan_button = self.button(ft.Icons.PAN_TOOL_OUTLINED, 'Mover vista', lambda e: self.set_pan(True))
        self.scale_button = self.button(ft.Icons.OPEN_IN_FULL, 'Escalar seleção · arraste a alça', self.activate_scale)
        self.grid_button = self.button(ft.Icons.GRID_ON, 'Grade', lambda e: self.toggle_option('grid_enabled'))
        self.grid_snap_button = self.button(ft.Icons.GRID_4X4, 'Ajustar à grade', lambda e: self.toggle_option('grid_snap'))
        self.align_button = self.button(ft.Icons.ALIGN_HORIZONTAL_CENTER, 'Alinhamento inteligente', lambda e: self.toggle_option('smart_align'))
        self.tools = ft.Row([
            ft.Row([self.select_button, self.pan_button, self.scale_button], spacing=0, tight=True),
            self.tool_separator(),
            ft.Row([self.grid_button, self.grid_snap_button, self.align_button], spacing=0, tight=True),
            self.tool_separator(),
            ft.Row([
            self.button(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, 'Importar imagens', self.actions.pick),
            self.button(ft.Icons.CONTENT_PASTE, 'Colar imagem', self.actions.paste),
            self.button(ft.Icons.CONTENT_COPY, 'Duplicar', self.actions.duplicate),
            self.button(ft.Icons.DELETE_OUTLINE, 'Excluir', self.actions.delete)], spacing=0, tight=True),
            self.tool_separator(),
            self.button(ft.Icons.FIT_SCREEN, 'Enquadrar', self.fit)], spacing=APP_PADDING,
            height=COMPACT_CONTROL_HEIGHT, tight=True)
        self.content = ft.Column([
            ft.Container(content=self.tools, alignment=ft.Alignment.CENTER), self.body,
        ], expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.configure()

    @staticmethod
    def tool_separator():
        return ft.VerticalDivider(width=1, thickness=1, color=BORDER)

    def sync_modal_input(self):
        active = self.transform_mode.active
        self.modal_capture.visible = active
        self.viewer.scale_enabled = not active
        if self.secondary_pan:
            self.secondary_pan.pan_enabled = not active and self.active and self.view.editable()
            self.secondary_pan.zoom_enabled = self.secondary_pan.pan_enabled
        if self.active:
            with retain_children(self.scene):
                self.view.page.update(self.viewer, self.modal_capture,
                    *([self.secondary_pan] if self.secondary_pan else []))

    @staticmethod
    def button(icon, title, handler):
        return ft.IconButton(icon=icon, tooltip=title, on_click=handler,
            icon_size=19, width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)

    def configure(self):
        options = self.view.settings.configuration.values['references']
        if self.options_key != options:
            self.grid_enabled, self.grid_snap, self.smart_align = options['grid'], options['grid_snap'], options['smart_align']
            self.options_key = options
        self.options = options
        self.body.bgcolor = options['background']
        self.viewer.min_scale, self.viewer.max_scale = options['min_zoom'] / 100, options['max_zoom'] / 100
        self.viewer.scale_factor = 240 / options['wheel_sensitivity']
        for image in self.images.values():
            image.cache_width = PREVIEW_SIDES[self.view.settings.configuration.values['system']['quality']]
        color = self.view.settings.configuration.values['appearance']['selection']
        self.box.border = ft.Border.all(1, color)
        self.box.bgcolor = ft.Colors.with_opacity(.14, color)
        self.paint()
        self.sync_tool_states()
        self.overlays.sync()

    def sync_tool_states(self):
        self.grid_button.selected = self.grid_enabled
        self.grid_snap_button.selected = self.grid_snap
        self.align_button.selected = self.smart_align
        for button in (self.grid_button, self.grid_snap_button, self.align_button):
            button.style = ft.ButtonStyle(animation_duration=0,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if button.selected else None)
        self.align_button.tooltip = 'Alinhar aos objetos não selecionados · ' + ('Ligado' if self.smart_align else 'Desligado')
        self.scale_button.disabled = not self.selection.ids

    def toggle_option(self, name):
        if self.gesture:
            self.cancel()
        setattr(self, name, not getattr(self, name))
        self.sync_tool_states()
        self.overlays.refresh_grid(publish=True)
        self.view.page.update(self.tools)
        self.focus()

    def activate_scale(self, e=None):
        self.set_pan(False)
        self.sync_selection_frame()
        self.view.page.update(self.selection_frame)
        self.focus()

    def sync_selection_frame(self, items=None):
        items = items if items is not None else tuple(item for item in self.view.board.references if item.id in self.selection.ids)
        self.selection_frame.visible = bool(items) and not self.pan_mode
        if not items:
            return
        left, top, right, bottom = bounds(items)
        self.selection_frame.left, self.selection_frame.top = left + self.extent.x, top + self.extent.y
        self.selection_frame.width, self.selection_frame.height = right - left, bottom - top
        color = self.view.settings.configuration.values['appearance']['selection']
        self.selection_border.border = ft.Border.all(1, color)

    def sync(self):
        items = self.view.board.references
        keys = {item.id for item in items}
        self.selection.replace(self.selection.ids & keys)
        for mapping in (self.cards, self.images, self.models):
            for key in tuple(mapping):
                if key not in keys:
                    del mapping[key]
        for item in items:
            if item.id not in self.cards:
                image = ft.Image(src=str(self.view.store.images / item.asset), fit=ft.BoxFit.CONTAIN,
                    gapless_playback=True,
                    cache_width=PREVIEW_SIDES[self.view.settings.configuration.values['system']['quality']])
                self.images[item.id] = image
                move = ft.GestureDetector(content=image, on_tap_down=lambda e, key=item.id: self.select(key),
                    on_tap=lambda e, key=item.id: self.tap(key),
                    on_pan_down=lambda e, key=item.id: self.object_press(key, e),
                    on_pan_start=lambda e, key=item.id: self.begin(key, e),
                    on_pan_update=self.move, on_pan_end=self.finish, on_pan_cancel=self.cancel,
                    drag_interval=DRAG_INTERVAL_MS, mouse_cursor=ft.MouseCursor.MOVE)
                self.cards[item.id] = ft.Container(content=RetainedStack(hold_updates=lambda: False,
                    controls=[ft.Container(left=0, right=0, top=0, bottom=0, content=move)]),
                    tooltip=item.title)
            if self.models.get(item.id) != item:
                card = self.cards[item.id]
                card.left, card.top, card.width, card.height = item.x + self.extent.x, item.y + self.extent.y, item.width, item.height
                self.images[item.id].src = str(self.view.store.images / item.asset)
                self.models[item.id] = item
        self.scene.controls = [self.background, self.overlays.grid_box,
            *(self.cards[item.id] for item in items), self.overlays.guide_box, self.selection_frame, self.box]
        self.scene.width, self.scene.height = self.extent.width, self.extent.height
        self.background.content.width, self.background.content.height = self.scene.width, self.scene.height
        self.paint()
        self.overlays.sync()
        self.sync_selection_frame()
        self.sync_tool_states()
        if self.drop:
            self.drop.session_token = self.view.session.directory.name
            self.drop.disabled = not self.active or not self.view.editable()
        if self.secondary_pan:
            self.secondary_pan.pan_enabled = self.active and self.view.editable() and self.gesture is None
            self.secondary_pan.zoom_enabled = self.secondary_pan.pan_enabled
            self.secondary_pan.zoom_modifiers = list(self.view.keymap.bindings(Action.DRAG_ZOOM))
            self.secondary_pan.zoom_sensitivity = self.options['wheel_sensitivity']

    def paint(self):
        color = self.view.settings.configuration.values['appearance']['selection']
        for key, card in self.cards.items():
            card.border = ft.Border.all(1, color if key in self.selection.ids else ft.Colors.TRANSPARENT)

    def publish_cards(self, ids):
        if self.active and self.view.active and not self.view.closing:
            cards = [self.cards[key] for key in ids if key in self.cards]
            if cards:
                with retain_children(*(card.content for card in cards)):
                    self.view.page.update(*cards)

    def focus(self):
        self.view.focus.request(self.keyboard, lambda: self.active and self.view.active and not self.view.closing)

    @explicit_updates
    def select(self, key, *, collapse=False):
        if not self.active or self.pan_mode or not self.view.editable():
            return
        previous = set(self.selection.ids)
        ids = {key} if collapse else previous ^ {key} if 'Shift' in self.modifiers else previous if key in previous else {key}
        self.selection.replace(ids, key)
        self.paint()
        self.publish_cards(previous | ids)
        self.selection_changed()
        self.focus()

    @explicit_updates
    def tap(self, key):
        if 'Shift' not in self.modifiers and len(self.selection.ids) > 1:
            self.select(key, collapse=True)

    @explicit_updates
    def clear(self, e=None):
        if self.pan_mode or not self.active or (e is not None and 'Shift' in self.modifiers):
            return
        previous = set(self.selection.ids)
        self.selection.replace(set())
        self.paint()
        self.publish_cards(previous)
        self.selection_changed()
        self.focus()

    @explicit_updates
    def hover(self, e):
        self.pointer = (e.local_position.x, e.local_position.y)

    def insertion_position(self):
        point = self.pointer or tuple((size / 2 - shift) / self.zoom for size, shift in zip(self.viewport, self.translation))
        return point[0] - self.extent.x, point[1] - self.extent.y

    @explicit_updates
    def object_press(self, key, e, resize=False):
        if self.active and not self.pan_mode and self.view.editable():
            self.object_pointer = (key, resize, getattr(e, 'local_position', None), e.global_position)

    @explicit_updates
    def begin(self, key, e, resize=False):
        if not self.active or self.pan_mode or not self.view.editable() or self.loading:
            return
        if key is not None and key not in self.selection.ids:
            self.select(key)
        self.camera_revision += 1
        originals = tuple(item for item in self.view.board.references if item.id in self.selection.ids)
        if not originals:
            return
        pressed, self.object_pointer = self.object_pointer, None
        local = getattr(e, 'local_position', None)
        point = e.global_position
        if pressed is not None and pressed[:2] == (key, resize):
            local, point = pressed[2:]
        self.gesture = dict(board=self.view.board, originals=originals, resize=resize,
            pointer=(local.x, local.y) if local is not None else (point.x, point.y),
            local_coordinates=local is not None, zoom=self.zoom, preview=originals,
            bounds=bounds(originals), alignment=AlignmentIndex.from_items(
                item for item in self.view.board.references if item.id not in self.selection.ids))
        self.focus()
        self.move(e)

    @explicit_updates
    def move(self, e):
        gesture = self.gesture
        if not gesture or 'originals' not in gesture:
            return
        if not self.active or self.view.board is not gesture['board']:
            self.cancel()
            return
        # Local coordinates already include the pointer-down camera inverse.
        local = getattr(e, 'local_position', None)
        if gesture['local_coordinates'] and local is not None:
            dx, dy = local.x - gesture['pointer'][0], local.y - gesture['pointer'][1]
        else:
            dx = (e.global_position.x - gesture['pointer'][0]) / gesture['zoom']
            dy = (e.global_position.y - gesture['pointer'][1]) / gesture['zoom']
        originals = gesture['originals']
        if gesture['resize']:
            if self.smart_align:
                preview, guides = gesture['alignment'].scale(originals, dx, dy,
                    self.options['align_distance'] / gesture['zoom'])
            else:
                preview = scale_selection(originals, dx, dy)
                guides = (None, None)
        else:
            dx, dy, guides = gesture['alignment'].snap(gesture['bounds'], dx, dy,
                self.options['align_distance'] / gesture['zoom'], smart=self.smart_align,
                grid=self.options['grid_spacing'] if self.grid_snap else None)
            dx = max(-MAX_REFERENCE_POSITION - min(item.x for item in originals),
                min(MAX_REFERENCE_POSITION - max(item.x for item in originals), dx))
            dy = max(-MAX_REFERENCE_POSITION - min(item.y for item in originals),
                min(MAX_REFERENCE_POSITION - max(item.y for item in originals), dy))
            preview = tuple(replace(item, x=item.x + dx, y=item.y + dy) for item in originals)
        gesture['preview'] = preview
        for item in preview:
            card = self.cards[item.id]
            card.left, card.top, card.width, card.height = item.x + self.extent.x, item.y + self.extent.y, item.width, item.height
        self.sync_selection_frame(preview)
        self.overlays.show_guides(guides)
        cards = [self.cards[item.id] for item in preview]
        with retain_children(*(card.content for card in cards)):
            self.view.page.update(*cards, self.selection_frame, self.overlays.guide_box)

    @explicit_updates
    async def finish(self, e=None):
        if not self.gesture or 'originals' not in self.gesture:
            return
        if e is not None and getattr(e, 'global_position', None) is not None:
            self.move(e)
        gesture, self.gesture = self.gesture, None
        if not gesture:
            return
        changed = {item.id: item for item in gesture['preview']}
        self.overlays.show_guides((None, None))
        await self.actions.commit((changed.get(item.id, item) for item in gesture['board'].references),
            'Escalar referências' if gesture['resize'] else 'Mover referências', expected=gesture['board'])

    @explicit_updates
    def cancel(self, e=None):
        if self.transform_mode.active:
            self.transform_mode.reset()
        self.gesture = None
        self.object_pointer = None
        self.box_pointer = None
        self.box.visible = False
        self.overlays.show_guides((None, None))
        self.models.clear()
        self.sync()
        if self.active:
            self.view.page.update(self.scene)

    @explicit_updates
    def box_press(self, e):
        self.box_pointer = (e.local_position.x, e.local_position.y)

    @explicit_updates
    def box_begin(self, e):
        if not self.pan_mode and self.active and self.view.editable():
            self.camera_revision += 1
            self.gesture = dict(start=self.box_pointer or (e.local_position.x, e.local_position.y), base=set(self.selection.ids))
            self.box_pointer = None

    @explicit_updates
    def box_move(self, e):
        if not self.gesture or 'start' not in self.gesture:
            return
        bounds = rectangle(self.gesture['start'], (e.local_position.x, e.local_position.y))
        self.box.left, self.box.top = bounds[:2]
        self.box.width, self.box.height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        self.box.visible = True
        self.view.page.update(self.box)

    @explicit_updates
    def box_end(self, e=None):
        if not self.gesture or 'start' not in self.gesture:
            return
        bounds = (self.box.left - self.extent.x, self.box.top - self.extent.y,
            self.box.left + (self.box.width or 0) - self.extent.x, self.box.top + (self.box.height or 0) - self.extent.y)
        previous = set(self.selection.ids)
        chosen = {item.id for item in self.view.board.references if intersects(bounds, (item.x, item.y, item.x + item.width, item.y + item.height))}
        self.selection.replace(chosen | self.gesture['base'] if 'Shift' in self.modifiers else chosen)
        self.gesture = None
        self.box.visible = False
        self.paint()
        self.publish_cards(previous | self.selection.ids)
        self.view.page.update(self.box)
        self.focus()
        self.selection_changed()

    def selection_changed(self):
        self.sync_selection_frame()
        self.sync_tool_states()
        self.view.page.update(self.selection_frame, self.tools)
        self.view.chrome.sync()
        self.view.page.update(self.view.chrome.content, self.view.chrome.status)

    @explicit_updates
    def set_pan(self, enabled):
        if self.gesture:
            self.cancel()
        self.pan_mode = enabled
        self.viewer.pan_enabled = enabled
        self.interaction.ignore_interactions = enabled
        self.select_button.selected, self.pan_button.selected = not enabled, enabled
        self.sync_selection_frame()
        if self.active:
            with retain_children(self.scene):
                self.view.page.update(self.viewer, self.tools)
            self.view.page.update(self.selection_frame)
            self.focus()

    @explicit_updates
    def resized(self, e):
        if e.width > 0 and e.height > 0:
            self.viewport = (e.width, e.height)
            self.layout_ready.set()
            self.overlays.refresh_grid(publish=True)

    @explicit_updates
    def secondary_navigation(self, e):
        if not self.active or not self.view.active or self.view.closing or self.gesture is not None:
            return
        if e.zoom <= 0 or not all(math.isfinite(value) for value in (e.zoom, e.translation_x, e.translation_y)):
            return
        self.camera_revision += 1
        self.camera_used = True
        self.zoom = self.gesture_zoom = e.zoom
        self.translation = (e.translation_x, e.translation_y)
        if isinstance(self.viewer, SpatialView):
            self.viewer.camera_zoom, self.viewer.camera_x, self.viewer.camera_y = e.zoom, e.translation_x, e.translation_y
        self.overlays.refresh_grid(publish=True)
        if e.moved:
            self.focus()

    @explicit_updates
    def camera_pose(self, e):
        if (not self.active or not self.view.active or self.view.closing or e.generation != self.viewer.camera_revision
                or not all(math.isfinite(value) for value in (e.zoom, e.x, e.y)) or e.zoom <= 0):
            return
        self.zoom = self.gesture_zoom = e.zoom
        self.translation = (e.x, e.y)
        self.viewer.camera_zoom, self.viewer.camera_x, self.viewer.camera_y = e.zoom, e.x, e.y
        self.overlays.refresh_grid(publish=True)

    def publish_camera(self, control):
        with retain_children(self.scene):
            self.view.page.update(control)

    @explicit_updates
    def camera_begin(self, e):
        if self.camera_applying:
            return
        self.camera_revision += 1
        self.camera_used = True
        self.gesture_zoom = self.zoom

    @explicit_updates
    def camera_move(self, e):
        if self.camera_applying or not e.scale or not math.isfinite(e.scale) or self.gesture:
            return
        zoom = max(self.viewer.min_scale, min(self.viewer.max_scale, self.gesture_zoom * e.scale))
        focal, delta = e.local_focal_point, e.focal_point_delta
        ratio = zoom / self.zoom
        dx, dy = (delta.x, delta.y) if self.viewer.pan_enabled else (0, 0)
        self.translation = tuple(p - (p - d - t) * ratio for p, d, t in
            zip((focal.x, focal.y), (dx, dy), self.translation))
        self.zoom = zoom
        self.overlays.refresh_grid(publish=True)

    async def fit(self, e=None, *, all_items=False):
        if not self.active or not self.view.active or self.view.closing:
            return
        if self.gesture:
            self.cancel()
        items = [item for item in self.view.board.references if all_items or not self.selection.ids or item.id in self.selection.ids]
        if not items:
            return
        left, top = min(item.x for item in items), min(item.y for item in items)
        right, bottom = max(item.x + item.width for item in items), max(item.y + item.height for item in items)
        zoom = max(self.viewer.min_scale, min(self.viewer.max_scale,
            (self.viewport[0] - 2 * REFERENCE_GAP) / (right - left),
            (self.viewport[1] - 2 * REFERENCE_GAP) / (bottom - top)))
        tx = self.viewport[0] / 2 - ((left + right) / 2 + self.extent.x) * zoom
        ty = self.viewport[1] / 2 - ((top + bottom) / 2 + self.extent.y) * zoom
        self.camera_revision += 1
        revision = self.camera_revision
        self.camera_applying = True
        try:
            applied = await apply_viewer_camera(self.viewer, zoom, tx, ty,
                current=lambda: self.active and self.view.active and not self.view.closing and revision == self.camera_revision,
                publish=self.publish_camera)
        finally:
            self.camera_applying = False
        if not applied:
            if self.active and revision == self.camera_revision:
                self.view.notify('O cliente não confirmou o enquadramento da vista.', 'warning')
            return
        self.zoom = self.gesture_zoom = zoom
        self.translation = (tx, ty)
        self.camera_used = True
        self.overlays.refresh_grid(publish=True)

    async def restore_camera(self, revision):
        # Fit from real layout measurements, not a fixed startup delay.
        try:
            await asyncio.wait_for(self.layout_ready.wait(), timeout=1)
        except TimeoutError:
            pass
        if not self.active or not self.view.active or self.view.closing or revision != self.camera_revision or self.gesture:
            return
        if self.view.board.references and not self.camera_used and self.options['initial_view'] == 'Enquadrar imagens':
            await self.fit(all_items=True)
            return
        zoom, (tx, ty) = self.zoom, self.translation
        await apply_viewer_camera(self.viewer, zoom, tx, ty,
            current=lambda: self.active and self.view.active and not self.view.closing and revision == self.camera_revision,
            publish=self.publish_camera)

    def restore(self):
        self.suspend_camera()
        self.layout_ready.clear()
        self.camera_task = self.view.page.run_task(self.restore_camera, self.camera_revision)

    def suspend_camera(self):
        self.camera_revision += 1
        if self.camera_task is not None:
            self.camera_task.cancel()
            self.camera_task = None
        self.modifiers.clear()
        self.transform_mode.point = None
        if self.temporary_pan is not None:
            previous, self.temporary_pan = self.temporary_pan, None
            self.set_pan(previous)

    async def execute(self, action):
        if self.transform_mode.active:
            if action == Action.CONFIRM:
                await self.transform_mode.confirm()
            elif action == Action.CANCEL:
                self.cancel()
            return
        if self.view.work_modes.execute(action):
            return
        from koma.editor.application_commands import DOCUMENT_ACTIONS
        if action in DOCUMENT_ACTIONS:
            return
        if action in (Action.MOVE, Action.SCALE_REFS):
            self.transform_mode.start(scale=action == Action.SCALE_REFS)
            return
        handlers = {Action.IMPORT_IMAGES: self.actions.pick, Action.PASTE: self.actions.paste,
            Action.DUPLICATE: self.actions.duplicate, Action.DELETE: self.actions.delete,
            Action.UNDO: self.view.graph.undo, Action.REDO: self.view.graph.redo,
            Action.FIT: self.fit, Action.FOCUS: self.fit}
        if action in handlers:
            if self.gesture:
                self.cancel()
            await handlers[action]()
        elif action == Action.ALL:
            self.selection.replace({item.id for item in self.view.board.references})
            self.paint()
            self.publish_cards(self.cards)
            self.selection_changed()
        elif action in (Action.NONE, Action.CANCEL):
            self.cancel() if self.gesture else self.clear()
        elif action in (Action.SELECT, Action.PAN):
            self.set_pan(action == Action.PAN)

    @explicit_updates
    async def key_down(self, e):
        if not self.active or not self.view.editable():
            return
        key = e.key.lower()
        for prefix, modifier in (('shift', 'Shift'), ('control', 'Ctrl'), ('alt', 'Alt'), ('meta', 'Meta')):
            if key.startswith(prefix):
                self.modifiers.add(modifier)
        action = self.view.keymap.resolve(e.key, self.modifiers,
            'move' if self.transform_mode.active else 'canvas')
        if self.transform_mode.active and action is None:
            fallback = self.view.keymap.resolve(e.key, (), 'move')
            if fallback in (Action.CONFIRM, Action.CANCEL):
                action = fallback
        if action == Action.TEMP_PAN and self.temporary_pan is None:
            self.temporary_pan = self.pan_mode
            self.set_pan(True)
            return
        await self.execute(action)

    @explicit_updates
    def key_up(self, e):
        if self.temporary_pan is not None and self.view.keymap.resolve(e.key, self.modifiers, 'canvas') == Action.TEMP_PAN:
            previous, self.temporary_pan = self.temporary_pan, None
            self.set_pan(previous)
        key = e.key.lower()
        for prefix, modifier in (('shift', 'Shift'), ('control', 'Ctrl'), ('alt', 'Alt'), ('meta', 'Meta')):
            if key.startswith(prefix):
                self.modifiers.discard(modifier)

    async def dropped(self, e):
        if (not self.active or not self.view.editable() or not self.view.can_accept_drop()
                or e.protocol != drop_runtime.PROTOCOL or e.session_token != self.view.session.directory.name):
            return
        from koma.documents.file_drop import project_drop_path
        try:
            path = project_drop_path(e.files)
            if path is not None:
                await self.view.open_project_path(path)
                return
            if not all(type(value) in (int, float) and math.isfinite(value) for value in (e.scene_x, e.scene_y)):
                raise ValueError('Posição de soltura inválida.')
            await self.actions.import_paths(e.files, (e.scene_x - self.extent.x, e.scene_y - self.extent.y))
        except (OSError, ValueError, RuntimeError) as exc:
            self.view.notify(f'Não foi possível importar: {exc}', 'warning')
