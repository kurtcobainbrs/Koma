"""Resizable presentation of the existing player; contains no document state."""
import flet as ft
from koma.ui.design import APP_PADDING
from koma.ui.splitter import Splitter
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.focus_requests import FocusListener
from koma.ui.scene_sidebar import SceneSidebar


class AnimaticWorkspace:
    def __init__(self, player, header):
        self.player = player
        minimum = player.strip.track.height + WORKSPACE_STYLE.timeline_chrome_height
        self.timeline = ft.Container(height=minimum, content=ft.Column(
            [player.controls, player.strip.content], spacing=APP_PADDING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH, expand=True))
        self.splitter = Splitter(player.view.page, self.timeline, horizontal=True,
            minimum=minimum, maximum=WORKSPACE_STYLE.timeline_maximum, reverse=True)
        player.preview_slot.expand = True
        self.sidebar = SceneSidebar(player)
        self.scene_splitter = Splitter(player.view.page, self.sidebar.content,
            minimum=WORKSPACE_STYLE.scenes_minimum, maximum=WORKSPACE_STYLE.scenes_maximum,
            stable=(self.sidebar.list,))
        self.scene_splitter.content.visible = self.sidebar.content.visible
        preview = ft.Column([header, player.preview_slot], expand=True,
            spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.body = ft.Row([self.sidebar.reopen, self.sidebar.content,
            self.scene_splitter.content, preview], expand=True, spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        player.keyboard = FocusListener(content=ft.Column(expand=True), on_key_up=player.key_up)
        self.content = self.body

    def sync_height(self):
        minimum = self.player.strip.track.height + WORKSPACE_STYLE.timeline_chrome_height
        self.splitter.minimum = minimum
        if not self.splitter.user_resized:
            self.timeline.height = minimum
        elif self.timeline.height < minimum:
            self.timeline.height = minimum
