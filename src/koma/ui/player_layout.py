"""Limites responsivos do player; a prévia ocupa o espaço restante por flex."""

from dataclasses import dataclass
from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT, PAGE_PADDING


@dataclass(frozen=True)
class PlayerLayout:
    maximum_width: float = 1100
    horizontal_fraction: float = .94
    vertical_fraction: float = .88
    dialog_inset: float = PAGE_PADDING * 2
    content_padding: float = PAGE_PADDING
    chrome_height: float = COMPACT_CONTROL_HEIGHT * 2 + APP_PADDING * 5

    def apply(self, page, content, preview_slot):
        width, height = getattr(page, 'width', None), getattr(page, 'height', None)
        has_width = type(width) in (int, float) and width > 0
        has_height = type(height) in (int, float) and height > 0
        content.width = min(self.maximum_width, width * self.horizontal_fraction,
            max(0, width - self.dialog_inset * 2 - self.content_padding * 2)) if has_width else self.maximum_width
        content.height = min(height * self.vertical_fraction,
            max(0, height - self.dialog_inset * 2 - self.chrome_height)) if has_height else None
        content.tight = not has_height
        preview_slot.expand = has_height
