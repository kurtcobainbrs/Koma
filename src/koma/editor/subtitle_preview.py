"""Prévia de legendas em segundo plano, com cache curto e descarte de tarefas antigas."""

import asyncio
from collections import OrderedDict
from io import BytesIO

import flet as ft

from koma.exports.subtitles import normalized, render_subtitle
from koma.editor.frame_format import FrameFormat


def preview_bytes(text, size=None):
    output = BytesIO()
    render_subtitle(text, size or FrameFormat().preview_size()).save(output, format='PNG')
    return output.getvalue()


class SubtitlePreview:
    def __init__(self, player):
        self.player = player
        self.revision = 0
        self.cache = OrderedDict()
        self.pending = None
        self.preparing = False
        self.image = ft.Image(src='', fit=ft.BoxFit.FILL, gapless_playback=True)
        self.content = ft.Container(content=self.image, visible=False, ignore_interactions=True)

    def set_text(self, text):
        self.revision += 1
        self.pending = None
        text = normalized(text)
        self.content.visible = False
        if not text:
            return
        key = (text, self.player.view.board.frame_format.preview_size())
        if key in self.cache:
            self.cache.move_to_end(key)
            self.image.src = self.cache[key]
            self.content.visible = True
        else:
            self.pending = (text, self.revision, key[1])
            if not self.preparing:
                self.preparing = True
                self.player.view.page.run_task(self.drain)

    async def drain(self):
        """Keep one render in flight and only the latest requested subtitle."""
        try:
            while self.pending is not None:
                request, self.pending = self.pending, None
                await self.prepare(*request)
        finally:
            self.preparing = False

    async def prepare(self, text, revision, size=None):
        try:
            size = size or self.player.view.board.frame_format.preview_size()
            data = await asyncio.to_thread(preview_bytes, text, size)
            if revision != self.revision or not self.player.opened or self.player.view.closing:
                return
            self.cache[(text, size)] = data
            while len(self.cache) > 8:
                self.cache.popitem(last=False)
            self.image.src = data
            self.content.visible = True
            self.player.view.page.update(self.content)
        except (OSError, ValueError) as exc:
            if revision == self.revision and self.player.opened:
                self.player.view.notify(f'Não foi possível exibir a legenda: {exc}', 'warning')

    def clear(self):
        self.revision += 1
        self.pending = None
        self.content.visible = False
