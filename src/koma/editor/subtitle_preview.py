"""Prévia de legendas em segundo plano, com cache curto e descarte de tarefas antigas."""

import asyncio
from collections import OrderedDict
from io import BytesIO

import flet as ft

from koma.exports.subtitles import normalized, render_subtitle


def preview_bytes(text):
    output = BytesIO()
    render_subtitle(text, (1280, 720)).save(output, format='PNG')
    return output.getvalue()


class SubtitlePreview:
    def __init__(self, player):
        self.player = player
        self.revision = 0
        self.cache = OrderedDict()
        self.image = ft.Image(src='', fit=ft.BoxFit.FILL, gapless_playback=True)
        self.content = ft.Container(content=self.image, visible=False, ignore_interactions=True)

    def set_text(self, text):
        self.revision += 1
        text = normalized(text)
        self.content.visible = False
        if not text:
            return
        if text in self.cache:
            self.cache.move_to_end(text)
            self.image.src = self.cache[text]
            self.content.visible = True
        else:
            self.player.view.page.run_task(self.prepare, text, self.revision)

    async def prepare(self, text, revision):
        try:
            data = await asyncio.to_thread(preview_bytes, text)
            if revision != self.revision or not self.player.opened or self.player.view.closing:
                return
            self.cache[text] = data
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
        self.content.visible = False
