"""Leitura e validação de temas JSON; nenhuma execução de código externo."""

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class ThemeConfig:
    name: str
    mode: str
    colors: dict[str, str]


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

