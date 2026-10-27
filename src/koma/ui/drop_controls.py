"""Protocolo Python da extensão Flutter; não depende de Win32 nem do modelo."""

from dataclasses import dataclass, field
from typing import Optional

import flet as ft
from koma.documents.audio import AUDIO_EXTENSIONS
from flet.controls.base_control import control
from flet.controls.control_event import Event, EventHandler


@dataclass(kw_only=True)
class ImageDropEvent(Event):
    protocol: int = 1
    session_token: str = ''
    files: list[str] = field(default_factory=list)
    node_id: Optional[str] = None
    scene_x: Optional[float] = None
    scene_y: Optional[float] = None
    origin_x: float = 0.0
    origin_y: float = 0.0


@control('koma_drop_surface')
class ImageDropSurface(ft.LayoutControl):
    content: Optional[ft.Control] = None
    session_token: str = ''
    origin_x: float = 0.0
    origin_y: float = 0.0
    documents_only: bool = False
    audio_extensions: list[str] = field(default_factory=lambda: list(AUDIO_EXTENSIONS))
    on_dropped: Optional[EventHandler[ImageDropEvent]] = None


@control('koma_drop_scene')
class ImageDropScene(ft.LayoutControl):
    content: Optional[ft.Control] = None


@control('koma_drop_node')
class ImageDropNode(ft.LayoutControl):
    content: Optional[ft.Control] = None
    node_id: str = ''
