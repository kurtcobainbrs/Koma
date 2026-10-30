"""Shared card measurements used by its widgets and connection anchors."""

from dataclasses import dataclass

from koma.ui.design import COMPACT_CONTROL_HEIGHT


@dataclass(frozen=True)
class NodeLayout:
    padding: float = 4
    border: float = 1
    spacing: float = 4
    header_height: float = COMPACT_CONTROL_HEIGHT
    footer_height: float = 22
    socket_size: float = 12
    scene_body_height: float = 64
    scene_width: float = 200

    @property
    def inset(self):
        return self.padding + self.border

    @property
    def socket_inset(self):
        return self.inset + self.socket_size / 2

    @property
    def socket_bottom(self):
        return self.inset + self.footer_height / 2

    def image_width(self, node_width):
        return node_width - self.inset * 2 - self.socket_size

    def height(self, body_height, *, compact=False):
        return self.inset * 2 + body_height + (0 if compact else self.header_height + self.footer_height + self.spacing * 2)

    def socket_y(self, total_height, *, compact=False):
        chrome = 0 if compact else self.header_height + self.footer_height + self.spacing * 2
        body = max(0, total_height - self.inset * 2 - chrome)
        return self.inset + (0 if compact else self.header_height + self.spacing) + body / 2


NODE_LAYOUT = NodeLayout()
