"""Prévia de legendas em segundo plano, com cache curto e descarte de tarefas antigas."""

import asyncio
from io import BytesIO

import flet as ft

from koma.exports.subtitles import normalized, render_subtitle
from koma.editor.frame_format import FrameFormat


def preview_bytes(text, size=None, options=None):
    output = BytesIO()
    render_subtitle(text, size or FrameFormat().preview_size(), options).save(output, format='PNG')
    return output.getvalue()


class SubtitlePreview:
    def __init__(self, player):
        self.player = player
        self.revision = 0
        self.cache = player.view.settings.preview_cache
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
        config = self.player.view.settings.configuration
        key = (text, self.player.view.board.frame_format.preview_size(), config.revision)
        if key in self.cache:
            self.cache.move_to_end(key)
            self.image.src = self.cache[key]
            self.content.visible = True
        else:
            self.pending = (text, self.revision, key[1], config.values, config.revision)
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

    async def prepare(self, text, revision, size=None, preferences=None, settings_revision=None):
        try:
            size = size or self.player.view.board.frame_format.preview_size()
            config = self.player.view.settings.configuration
            preferences = preferences or config.values
            settings_revision = config.revision if settings_revision is None else settings_revision
            data = await asyncio.to_thread(preview_bytes, text, size, preferences['subtitles'])
            if revision != self.revision or not self.player.opened or self.player.view.closing:
                return
            self.cache[(text, size, settings_revision)] = data
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
