"""Famílias, pesos e escala de leitura compartilhados pela interface."""

from importlib.resources import files

import flet as ft

FONT_REGULAR = "Archivo"
FONT_BODY = "Archivo Medium"
FONT_HEADING = "Archivo SemiBold"
TEXT_SMALL = 12
TEXT_BODY = 13
TEXT_SECTION = 14
TEXT_TITLE = 18


def register_fonts(page: ft.Page) -> None:
    root = files("koma").joinpath("assets", "fonts")
    page.fonts = {
        FONT_REGULAR: str(root.joinpath("Archivo-Regular.ttf")),
        FONT_BODY: str(root.joinpath("Archivo-Medium.ttf")),
        FONT_HEADING: str(root.joinpath("Archivo-SemiBold.ttf")),
    }


def body_style(size: int = TEXT_BODY) -> ft.TextStyle:
    return ft.TextStyle(font_family=FONT_BODY, size=size, weight=ft.FontWeight.W_500, height=1.35)


def heading_style(size: int = TEXT_SECTION) -> ft.TextStyle:
    return ft.TextStyle(font_family=FONT_HEADING, size=size, weight=ft.FontWeight.W_600, height=1.25)


def text_theme() -> ft.TextTheme:
    return ft.TextTheme(
        body_large=body_style(TEXT_SECTION), body_medium=body_style(), body_small=body_style(TEXT_SMALL),
        label_large=heading_style(TEXT_BODY), label_medium=body_style(), label_small=body_style(TEXT_SMALL),
        title_large=heading_style(TEXT_TITLE), title_medium=heading_style(), title_small=heading_style(),
        headline_small=heading_style(TEXT_TITLE),
    )
