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

    @property
    def inset(self):
        return self.padding + self.border

    @property
    def socket_inset(self):
        return self.inset + self.socket_size / 2

    @property
    def socket_bottom(self):
        return self.inset + self.footer_height / 2

    def height(self, body_height):
        return self.inset * 2 + self.header_height + body_height + self.footer_height + self.spacing * 2


NODE_LAYOUT = NodeLayout()
