"""Shared presentation measurements for the approved Canvas/Animatic design."""
from dataclasses import dataclass
from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT, CONTROL_HEIGHT, PAGE_PADDING
from koma.editor.animatic_settings import SCENES_WIDTH, SCENES_MINIMUM, SCENES_MAXIMUM


@dataclass(frozen=True)
class WorkspaceStyle:
    inspector_width: float = 320
    media_panel_width: float = 248
    media_panel_minimum: float = 220
    media_panel_maximum: float = 380
    inspector_minimum: float = 260
    inspector_maximum: float = 520
    mode_button_width: float = 90
    mode_tab_width: float = 76
    scene_choice_width: float = 144
    scenes_width: float = SCENES_WIDTH
    scenes_minimum: float = SCENES_MINIMUM
    scenes_maximum: float = SCENES_MAXIMUM
    media_row_height: float = CONTROL_HEIGHT + PAGE_PADDING
    media_thumbnail_width: float = 64
    slider_width: float = 112
    track_label_width: float = 96
    ruler_height: float = COMPACT_CONTROL_HEIGHT
    marker_height: float = COMPACT_CONTROL_HEIGHT
    sequence_height: float = COMPACT_CONTROL_HEIGHT - APP_PADDING * 2
    reference_cell_maximum: float = 240
    picture_height: float = CONTROL_HEIGHT * 3
    picture_caption_height: float = COMPACT_CONTROL_HEIGHT
    audio_height: float = CONTROL_HEIGHT + APP_PADDING
    timeline_chrome_height: float = COMPACT_CONTROL_HEIGHT * 2 + APP_PADDING * 3
    timeline_maximum: float = 900


WORKSPACE_STYLE = WorkspaceStyle()
