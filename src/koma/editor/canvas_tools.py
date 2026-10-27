"""Ferramentas do canvas: apresentação, atalho e gestos declarados no mesmo lugar."""

from dataclasses import dataclass
from collections.abc import Callable

import flet as ft
from koma.editor.shortcuts import Action


@dataclass(frozen=True)
class CanvasTool:
    key: str
    action: str
    label: str
    icon: ft.IconData
    cursor: ft.MouseCursor
    hint: str
    edit_nodes: bool = False
    pan: bool = False
    press: Callable | None = None
    begin: Callable | None = None
    update: Callable | None = None
    end: Callable | None = None
    cancel: Callable | None = None


def canvas_tools(workspace):
    zoom, links = workspace.box_zoom, workspace.links
    return (
        CanvasTool('select', Action.SELECT, 'Seleção', ft.Icons.NEAR_ME_OUTLINED, ft.MouseCursor.BASIC,
            'Seleção: arraste no fundo para criar uma caixa. Use os modificadores de seleção para adicionar ou remover nodes. Arraste um cabeçalho para mover o grupo.',
            edit_nodes=True, cancel=workspace.box_selection.cancel),
        CanvasTool('pan', Action.PAN, 'Pan', ft.Icons.PAN_TOOL_OUTLINED, ft.MouseCursor.GRAB,
            'Pan: arraste em qualquer área do canvas para navegar, sem mover os quadros.', pan=True),
        CanvasTool('zoom', Action.ZOOM, 'Zoom por caixa', ft.Icons.CROP_FREE, ft.MouseCursor.PRECISE,
            'Zoom: arraste uma caixa para enquadrar a área. Use Cancelar para interromper; botão direito reduz. A roda continua disponível.',
            press=zoom.press, begin=zoom.begin, update=zoom.update, end=zoom.end,
            cancel=zoom.cancel),
        CanvasTool('cut', Action.CUT, 'Cortar ligações', ft.Icons.CONTENT_CUT, ft.MouseCursor.PRECISE,
            'Cortar ligações: arraste sobre os fios. Use Cancelar para interromper; Use Desfazer para restaurar.',
            begin=links.cut_begin, update=links.cut_update, end=links.cut_end, cancel=links.cancel_cut),
    )
