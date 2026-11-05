"""Leitura e validação de temas JSON; nenhuma execução de código externo."""

import json
import re
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class ThemeConfig:
    name: str
    mode: str
    colors: dict[str, str]


def accent_theme(config, accent):
    """Derive all interactive color roles; preserve surfaces and semantic colors."""
    if not isinstance(accent, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        raise ValueError('Use uma cor no formato #RRGGBB.')
    if accent.upper() == config.colors['primary'].upper():
        return config

    def rgb(color):
        return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))

    def blend(first, second, amount):
        return '#' + ''.join(f'{round(a * amount + b * (1 - amount)):02X}'
            for a, b in zip(rgb(first), rgb(second)))

    def luminance(color):
        channels = (channel / 255 for channel in rgb(color))
        return sum(weight * (channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4)
            for weight, channel in zip((.2126, .7152, .0722), channels))

    def foreground(background):
        def contrast(color):
            values = sorted((luminance(background), luminance(color)))
            return (values[1] + .05) / (values[0] + .05)
        return max((config.colors['surface_dim'], config.colors['on_surface']), key=contrast)

    colors = dict(config.colors)
    container = blend(accent, colors['surface'], .24)
    fixed = blend(accent, colors['on_surface'], .35)
    for role in ('primary', 'secondary'):
        colors.update({role: accent, f'on_{role}': foreground(accent),
            f'{role}_container': container, f'on_{role}_container': foreground(container),
            f'{role}_fixed': fixed, f'{role}_fixed_dim': accent,
            f'on_{role}_fixed': foreground(fixed), f'on_{role}_fixed_variant': foreground(fixed)})
    return replace(config, colors=colors)


def load_theme(path: str = "") -> ThemeConfig:
    try:
        default = json.loads(files("koma").joinpath("themes", "koma-dark.json").read_text(encoding="utf-8"))
        raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8")) if path else default
        if not isinstance(raw, dict) or raw.get("version") != 1:
            raise ValueError("O tema deve ter version igual a 1.")
        if not isinstance(raw.get("name"), str) or not raw["name"].strip():
            raise ValueError("Informe o nome do tema.")
        if raw.get("mode", "dark") not in {"dark", "light"}:
            raise ValueError("mode deve ser dark ou light.")
        overrides = raw.get("colors", {})
        if not isinstance(overrides, dict):
            raise ValueError("colors deve ser um objeto.")
        for key, color in overrides.items():
            if key not in default["colors"]:
                raise ValueError(f"Cor desconhecida: {key}")
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", color):
                raise ValueError(f"Cor inválida em {key}: use #RRGGBB ou #AARRGGBB.")
        return ThemeConfig(raw["name"], raw.get("mode", "dark"), default["colors"] | overrides)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Não foi possível carregar o tema: {exc}") from exc

