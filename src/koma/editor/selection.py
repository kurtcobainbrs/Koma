"""Estado de seleção e caixa no espaço do canvas, independente da persistência."""

from dataclasses import dataclass, field

import flet as ft

from koma.ui.design import DRAG_INTERVAL_MS
from koma.editor.geometry import NODE_HEIGHT, NODE_WIDTH
from koma.editor.shortcuts import Action


@dataclass
class NodeSelection:
    ids: set[str] = field(default_factory=set)
    active: str | None = None

    def replace(self, identifiers, active=None):
        self.ids = set(identifiers)
        self.active = active if active in self.ids else self.active if self.active in self.ids else next(iter(sorted(self.ids)), None)


def rectangle(start, end):
    return min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1])


def intersects(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


class BoxSelection:
    def __init__(self, workspace):
        self.workspace, self.view = workspace, workspace.view
        self.start = None
        self.pending = None
        self.base = set()
        self.active_before = None
        self.operation = 'replace'
        self.overlay = ft.Container(left=0, top=0, width=0, height=0, visible=False,
            ignore_interactions=True, border=ft.Border.all(1, ft.Colors.SECONDARY),
            bgcolor=ft.Colors.with_opacity(.14, ft.Colors.SECONDARY))

    @property
    def active(self):
        return self.start is not None

    def press(self, e):
        nav = self.workspace.navigation
        if nav.effective_mode == 'select' and not self.view.busy:
            self.pending = (e.local_position.x, e.local_position.y), set(nav.selection.ids), nav.selected

    def begin(self, e):
        nav = self.workspace.navigation
        if nav.effective_mode != 'select' or not self.view.editable() or self.workspace.drag:
            return
        self.start, self.base, self.active_before = self.pending or (
            (e.local_position.x, e.local_position.y), set(nav.selection.ids), nav.selected)
        self.pending = None
        self.operation = 'subtract' if nav.modifier(Action.SUBTRACT_SELECTION) else 'add' if nav.modifier(Action.ADD_SELECTION) else 'replace'
        self.workspace.viewer.scale_enabled = False
        nav.focus_keyboard()
        self.update(e)

    def update(self, e):
        if not self.active or self.view.closing:
            return
        rect = rectangle(self.start, (e.local_position.x, e.local_position.y))
        self.overlay.left, self.overlay.top = rect[:2]
        self.overlay.width, self.overlay.height = rect[2] - rect[0], rect[3] - rect[1]
        self.overlay.visible = True
        hits = set()
        for identifier, card in self.view.cards.items():
            node = card.content
            bounds = node.left, node.top, node.left + NODE_WIDTH, node.top + self.workspace.node_heights.get(identifier, NODE_HEIGHT)
            if intersects(rect, bounds):
                hits.add(identifier)
        identifiers = self.base | hits if self.operation == 'add' else self.base - hits if self.operation == 'subtract' else hits
        self.workspace.navigation.apply_selection(identifiers)
        self.view.page.update(self.overlay)

    def end(self, e=None):
        if not self.active:
            self.pending = None
            return
        self.start = self.pending = None
        self.overlay.visible = False
        self.workspace.navigation.sync(update=False)
        if not self.view.closing:
            self.view.page.update(self.overlay, self.workspace.viewer)

    def cancel(self, e=None):
        if self.active:
            self.workspace.navigation.apply_selection(self.base, self.active_before)
        self.end()

    def bind(self, gesture):
        gesture.drag_interval = DRAG_INTERVAL_MS
        gesture.on_pan_down = self.press
        gesture.on_pan_start = self.begin
        gesture.on_pan_update = self.update
        gesture.on_pan_end = self.end
        gesture.on_pan_cancel = self.cancel
