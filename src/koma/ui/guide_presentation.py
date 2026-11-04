"""Latest-only, cached overlay rendering away from playback/pointer handlers."""
import asyncio
from io import BytesIO
import flet as ft
from koma.exports.guides import render_guides


def overlay_bytes(camera, size, options):
    buffer = BytesIO()
    render_guides(camera, size, options).save(buffer, format='PNG')
    return buffer.getvalue()


class GuidePresentation:
    def __init__(self, player):
        self.player = player
        self.image = ft.Image(src='', fit=ft.BoxFit.FILL, gapless_playback=True)
        self.content = ft.Container(left=0, top=0, right=0, bottom=0,
            content=self.image, visible=False, ignore_interactions=True)
        self.key = self.pending = None
        self.running = False

    def sync(self):
        player = self.player
        frame = player.timeline.frames[player.current] if player.timeline and 0 <= player.current < len(player.timeline.frames) else None
        options = player.view.settings.configuration.values['guides']
        enabled = frame and (options['preview'] or (options['camera_preview'] and frame.camera.visible and frame.camera.preset != 'none'))
        if not enabled:
            self.key = self.pending = None
            self.content.visible = False
            return
        size = player.view.board.frame_format.preview_size()
        key = ('guide-overlay', frame.camera, size, tuple(options.items()))
        if key == self.key and (self.content.visible or self.pending is not None or self.running):
            return
        self.key = key
        cache = player.view.settings.preview_cache
        if key in cache:
            self.image.src = cache[key]
            self.content.visible = True
            return
        self.content.visible = False
        self.pending = (key, frame.camera, size, dict(options))
        if not self.running:
            self.running = True
            player.view.page.run_task(self.drain)

    async def drain(self):
        try:
            while self.pending:
                key, camera, size, options = self.pending
                self.pending = None
                data = await asyncio.to_thread(overlay_bytes, camera, size, options)
                if key != self.key or not self.player.presenting:
                    continue
                self.player.view.settings.preview_cache[key] = data
                self.image.src = data
                self.content.visible = True
                self.player.view.page.update(self.content)
        except (OSError, ValueError):
            if self.player.presenting:
                self.player.view.notify('Não foi possível preparar as guias.', 'warning')
        finally:
            self.running = False

    async def preferences(self, e=None):
        if self.player.editing:
            self.player.view.notify('Conclua ou cancele o ajuste atual.', 'info')
            return
        from koma.ui.preferences_panel import PreferencesPanel
        from koma.preference_catalog import CATEGORIES
        panel = PreferencesPanel(self.player.view)
        await panel.open()
        panel.select(next(category for category in CATEGORIES if category.key == 'guides'))
