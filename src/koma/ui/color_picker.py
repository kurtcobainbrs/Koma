"""Seletor HSV: roda de matiz/saturação, valor e cores rápidas."""

from collections.abc import Callable
import colorsys
import math

import flet as ft

from koma.ui.typography import TEXT_BODY
from koma.ui.design import dialog, BORDER, CONTROL_HEIGHT, RADIUS


def rgb_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(channel * 255):02X}" for channel in rgb)


class ColorPicker:
    WHEEL_SIZE = 220

    def __init__(self, page: ft.Page, title: str, color: str, on_apply: Callable[[str], bool | None],
                 on_preview: Callable[[str], None] | None = None,
                 on_cancel: Callable[[], None] | None = None):
        self.page, self.on_apply = page, on_apply
        self.on_preview, self.on_cancel = on_preview, on_cancel
        self.settled = False
        self.hue, self.saturation, self.brightness = self.parse(color)
        self.preview = ft.Container(height=36, bgcolor=self.value, border_radius=RADIUS,
                                    border=ft.Border.all(1, BORDER))
        self.marker = ft.Container(width=14, height=14, bgcolor=self.value,
            border_radius=7, border=ft.Border.all(2, ft.Colors.WHITE),
            shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK))
        wheel = ft.Stack([
            self.circle(gradient=ft.SweepGradient(colors=[
                rgb_hex(colorsys.hsv_to_rgb(index / 6, 1, 1)) for index in range(7)])),
            self.circle(gradient=ft.RadialGradient(colors=[
                ft.Colors.WHITE, ft.Colors.with_opacity(0, ft.Colors.WHITE)], radius=0.5)),
            self.marker,
        ], width=self.WHEEL_SIZE, height=self.WHEEL_SIZE, clip_behavior=ft.ClipBehavior.NONE)
        self.wheel = ft.GestureDetector(content=wheel, mouse_cursor=ft.MouseCursor.CLICK,
            on_tap_down=self.pick, on_pan_start=self.pick, on_pan_update=self.pick,
            tooltip="Escolha o tom ao redor e a intensidade pela distância do centro.")
        self.value_slider = ft.Slider(min=0, max=100, divisions=100, value=self.brightness * 100,
            label="{value}%", on_change=self.change_value, expand=True)
        self.dialog = dialog(
            title=ft.Text(title),
            content=ft.Column([
                ft.Row([self.wheel], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("Luminosidade", size=TEXT_BODY),
                ft.Row([self.value_slider]), self.preview,
                ft.Text("Cores rápidas", size=TEXT_BODY),
                ft.Row([ft.Container(width=24, height=24, bgcolor=quick, border_radius=RADIUS,
                    border=ft.Border.all(1, BORDER), on_click=lambda e, c=quick: self.select(c))
                    for quick in self.palette()], wrap=True, spacing=6, run_spacing=6),
            ], width=320, height=440, scroll=ft.ScrollMode.AUTO, spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            on_dismiss=self.dismiss,
            actions=[ft.TextButton("Cancelar", height=CONTROL_HEIGHT, on_click=self.cancel),
                     ft.FilledButton("Aplicar cor", height=CONTROL_HEIGHT, on_click=self.apply)],
        )
        self.refresh(update=False)

    def circle(self, **kwargs) -> ft.Container:
        return ft.Container(width=self.WHEEL_SIZE, height=self.WHEEL_SIZE,
                            border_radius=self.WHEEL_SIZE / 2, **kwargs)

    @staticmethod
    def parse(color: str) -> tuple[float, float, float]:
        rgb = color[-6:]
        return colorsys.rgb_to_hsv(*(int(rgb[index:index + 2], 16) / 255 for index in (0, 2, 4)))

    @property
    def value(self) -> str:
        return rgb_hex(colorsys.hsv_to_rgb(self.hue, self.saturation, self.brightness))

    def pick(self, e) -> None:
        position = e.local_position
        if position is None:
            return
        radius = self.WHEEL_SIZE / 2
        x, y = position.x - radius, position.y - radius
        self.hue = (math.atan2(y, x) / math.tau) % 1
        self.saturation = min(1, math.hypot(x, y) / radius)
        self.refresh()

    def change_value(self, e) -> None:
        self.brightness = max(0, min(1, float(e.control.value) / 100))
        self.refresh()

    def refresh(self, update: bool = True) -> None:
        radius = self.WHEEL_SIZE / 2
        angle = self.hue * math.tau
        self.marker.left = radius + math.cos(angle) * radius * self.saturation - 7
        self.marker.top = radius + math.sin(angle) * radius * self.saturation - 7
        self.marker.bgcolor = self.value
        self.value_slider.value = self.brightness * 100
        self.preview.bgcolor = self.value
        if update:
            if self.on_preview and not self.settled:
                self.on_preview(self.value)
            self.page.update()

    @staticmethod
    def palette() -> list[str]:
        values = [colorsys.hsv_to_rgb(hue / 12, 0.65, 0.85) for hue in range(12)]
        values += [(value / 5,) * 3 for value in range(6)]
        return [rgb_hex(rgb) for rgb in values]

    def select(self, color: str) -> None:
        self.hue, self.saturation, self.brightness = self.parse(color)
        self.refresh()

    def apply(self, e) -> None:
        if self.settled:
            return
        self.settled = True
        if self.on_apply(self.value) is False and self.on_cancel:
            self.on_cancel()
            self.page.update()
        self.page.pop_dialog()

    def dismiss(self, e) -> None:
        if self.settled:
            return
        self.settled = True
        if self.on_cancel:
            self.on_cancel()
        self.page.update()

    def cancel(self, e) -> None:
        if not self.settled:
            self.dismiss(e)
            self.page.pop_dialog()

    def open(self) -> None:
        self.page.show_dialog(self.dialog)
