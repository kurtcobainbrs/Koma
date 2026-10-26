"""Tokens visuais e componentes compartilhados da interface."""

import flet as ft

from koma.ui.theme import ThemeConfig, load_theme
from koma.ui.typography import FONT_BODY, TEXT_BODY, body_style, heading_style, text_theme, TEXT_SMALL, FONT_HEADING, TEXT_TITLE


BACKGROUND = ft.Colors.SURFACE_CONTAINER_LOW
SURFACE = ft.Colors.SURFACE
BORDER = ft.Colors.OUTLINE_VARIANT
MUTED = ft.Colors.ON_SURFACE_VARIANT
ACCENT = ft.Colors.PRIMARY
PROGRESS = ft.Colors.TERTIARY
PROGRESS_ERROR = ft.Colors.ERROR
TAB_BAR = ft.Colors.SURFACE_CONTAINER_LOWEST
TEXT = ft.Colors.ON_SURFACE
BRAND_BACKGROUND = ft.Colors.SCRIM
SELECTION = ft.Colors.PRIMARY_CONTAINER
ON_SELECTION = ft.Colors.ON_PRIMARY_CONTAINER
RADIUS = 5
CONTROL_HEIGHT = 34
COMPACT_CONTROL_HEIGHT = 28
PATH_CONTROL_HEIGHT = 48
ICON_SIZE = 18
PAGE_PADDING = 12
APP_PADDING = 4
EDITOR_SURFACE_PADDING = 6
EDITOR_SURFACE_BORDER = 1
PANEL_PADDING = 10
PROGRESS_HEIGHT = 6
DRAG_INTERVAL_MS = 16


def input_style(height: int = CONTROL_HEIGHT) -> dict:
    """Dimensões e bordas compartilhadas por campos e listas suspensas."""
    return dict(
        height=height, dense=True, text_size=TEXT_BODY, text_style=body_style(),
        label_style=body_style(), content_padding=8,
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                border_radius=RADIUS, side=ft.BorderSide(1, BORDER)),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                border_radius=RADIUS, side=ft.BorderSide(1, ft.Colors.OUTLINE)),
        },
    )


def progress_bar(**kwargs) -> ft.ProgressBar:
    """Cor semântica e trilho neutro, independentes da seleção do projeto."""
    defaults = dict(height=PROGRESS_HEIGHT, bar_height=PROGRESS_HEIGHT,
                    color=PROGRESS, bgcolor=BORDER, border_radius=RADIUS / 2)
    return ft.ProgressBar(**(defaults | kwargs))


def app_theme(config: ThemeConfig | None = None) -> ft.Theme:
    config = config or load_theme()
    button = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=RADIUS),
        padding=ft.Padding.symmetric(horizontal=12, vertical=0),
        text_style=heading_style(TEXT_BODY), icon_size=ICON_SIZE,
        visual_density=ft.VisualDensity.COMPACT,
    )
    icon = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=RADIUS),
        padding=0, icon_size=ICON_SIZE, visual_density=ft.VisualDensity.COMPACT,
    )
    return ft.Theme(
        font_family=FONT_BODY, text_theme=text_theme(),
        color_scheme=ft.ColorScheme(**config.colors),
        button_theme=ft.ButtonTheme(style=button),
        filled_button_theme=ft.FilledButtonTheme(style=button),
        outlined_button_theme=ft.OutlinedButtonTheme(style=button),
        text_button_theme=ft.TextButtonTheme(style=button),
        icon_button_theme=ft.IconButtonTheme(style=icon),
    )


def dialog(**kwargs) -> ft.AlertDialog:
    """Popups fecham por Esc/toque externo; ações exigem clique explícito."""
    defaults = dict(
        modal=False, bgcolor=SURFACE, shape=ft.RoundedRectangleBorder(radius=RADIUS),
        title_padding=ft.Padding.only(left=20, right=20, top=16, bottom=10),
        content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
        actions_padding=ft.Padding.only(left=20, right=20, top=8, bottom=12),
        title_text_style=heading_style(TEXT_TITLE), content_text_style=body_style(),
    )
    return ft.AlertDialog(**(defaults | kwargs))
