"""Canvas interface controls backed by the current sequence's entry/exit data."""
import flet as ft
from koma.editor.group_ports import GroupPort
from koma.editor.geometry import GRID_STEP, NODE_HEIGHT
from koma.ui.design import APP_PADDING, BORDER, COMPACT_CONTROL_HEIGHT, SURFACE
from koma.ui.node_layout import NODE_LAYOUT
from koma.ui.typography import TEXT_SMALL


class SequencePorts:
    def __init__(self, workspace):
        self.workspace = workspace
        self.boxes = {}

    def sync(self):
        ws = self.workspace
        identifier = ws.scope.active
        if identifier is None:
            self.boxes = {}
            return
        refs = (GroupPort(identifier), GroupPort(identifier, True))
        self.boxes = {ref: self.boxes.get(ref) or ft.Container(width=NODE_LAYOUT.scene_width,
            height=COMPACT_CONTROL_HEIGHT + APP_PADDING * 2, padding=NODE_LAYOUT.padding,
            bgcolor=SURFACE, border=ft.Border.all(NODE_LAYOUT.border, BORDER), border_radius=APP_PADDING)
            for ref in refs}
        bounds = [ws.links.bounds(key) for key in ws.scope.visible]
        left = min((box[0] for box in bounds), default=ws.extent.origin_x + GRID_STEP * 5)
        right = max((box[2] for box in bounds), default=left + NODE_LAYOUT.scene_width)
        top = min((box[1] for box in bounds), default=ws.extent.origin_y + GRID_STEP * 2)
        for ref, box in self.boxes.items():
            box.left = right + GRID_STEP * 2 if ref.output else max(0, left - box.width - GRID_STEP * 2)
            box.top = top + NODE_HEIGHT / 2 - box.height / 2
            if box.content is None:
                label = ft.Text('Saída' if ref.output else 'Entrada', size=TEXT_SMALL, expand=True)
                socket = ws.links.socket(ref, not ref.output)
                box.content = ft.Row([socket, label] if ref.output else [label, socket], spacing=APP_PADDING)

    def bounds(self, ref):
        box = self.boxes[ref]
        return box.left, box.top, box.left + box.width, box.top + box.height

    def controls(self):
        return list(self.boxes.values())
