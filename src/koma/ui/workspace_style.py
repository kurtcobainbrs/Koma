"""Shared presentation measurements for the approved Canvas/Animatic design."""
from dataclasses import dataclass
from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT, CONTROL_HEIGHT, PAGE_PADDING


@dataclass(frozen=True)
class WorkspaceStyle:
    inspector_width: float = 320
    inspector_minimum: float = 260
    inspector_maximum: float = 520
    mode_button_width: float = 90
    scene_choice_width: float = 144
    media_row_height: float = CONTROL_HEIGHT + PAGE_PADDING
    media_thumbnail_width: float = 64
    slider_width: float = 112
    track_label_width: float = 96
    ruler_height: float = COMPACT_CONTROL_HEIGHT
    marker_height: float = COMPACT_CONTROL_HEIGHT
    sequence_height: float = COMPACT_CONTROL_HEIGHT - APP_PADDING * 2
    picture_height: float = CONTROL_HEIGHT * 3
    picture_caption_height: float = COMPACT_CONTROL_HEIGHT
    audio_height: float = CONTROL_HEIGHT + APP_PADDING
    timeline_chrome_height: float = COMPACT_CONTROL_HEIGHT * 2 + APP_PADDING * 3
    timeline_maximum: float = 900


WORKSPACE_STYLE = WorkspaceStyle()
