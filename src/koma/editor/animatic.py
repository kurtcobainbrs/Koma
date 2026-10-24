"""Reprodução temporizada por relógio monotônico; usa imagens já em memória."""

import asyncio
from bisect import bisect_right
from time import monotonic

import flet as ft

from koma.ui.design import CONTROL_HEIGHT, MUTED, dialog
from koma.ui.typography import FONT_HEADING, TEXT_BODY, TEXT_SMALL
from koma.editor.graph import ordered
from koma.editor.framing import ImageViewport
from koma.editor.scenes import principal, scene_frames
from koma.editor.subtitle_preview import SubtitlePreview


class Timeline:
    def __init__(self, board, active=None):
        board = ordered(board)
        self.root = principal(board, active)
        has_scenes = any(frame.node_type.starts_scene for frame in board.frames)
        sequence = scene_frames(board, self.root) if self.root else () if has_scenes else board.frames
        self.frames = tuple(frame for frame in sequence if frame.node_type.timed)
        self.starts = []
        self.total = 0.0
        for frame in self.frames:
            self.starts.append(self.total)
            self.total += frame.duration

    def index_at(self, seconds):
        return max(0, min(len(self.frames)-1, bisect_right(self.starts, seconds)-1))


class AnimaticPlayer:
    def __init__(self, view):
        self.view = view
        self.opened = self.playing = False
        self.dismiss_pending = False
        self.position = 0.0
        self.anchor = 0.0
        self.current = -1
        self.task = None
        self.timeline = None
        self.preview = ImageViewport(view, height=400)
        self.subtitles = SubtitlePreview(self)
        self.screen = ft.Container(aspect_ratio=16/9, content=ft.Stack(
            [self.preview.content, self.subtitles.content], fit=ft.StackFit.EXPAND))
        self.caption = ft.Text(size=TEXT_BODY, font_family=FONT_HEADING, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        self.clock = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.play = ft.IconButton(icon=ft.Icons.PLAY_ARROW, tooltip='Reproduzir', on_click=self.toggle)
        self.slider = ft.Slider(min=0, max=1, value=0, expand=True, on_change=self.seek,
            on_change_start=self.seek_start, on_change_end=self.seek_end)
        self.loop = ft.Checkbox(label='Repetir', value=False)
        self.show_subtitles = ft.Checkbox(label='Legendas', value=True, on_change=self.toggle_subtitles,
            tooltip='Mostrar ou ocultar no player. A inclusão no MP4 é escolhida na exportação.')
        self.controls = ft.Row([
            ft.IconButton(icon=ft.Icons.SKIP_PREVIOUS, tooltip='Quadro anterior', on_click=self.previous), self.play,
            ft.IconButton(icon=ft.Icons.SKIP_NEXT, tooltip='Próximo quadro', on_click=self.next), self.slider,
            self.clock], spacing=4)
        self.content = ft.Column([self.screen, self.caption, self.controls,
            ft.Row([ft.Text('Ordem do fluxo · cortes diretos · sem áudio', size=TEXT_SMALL, color=MUTED),
                ft.Row([self.show_subtitles, self.loop], tight=True, spacing=8)],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN)], width=800, tight=True, spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.popup = dialog(title=ft.Text('Animatic'), content=self.content,
            on_dismiss=self.dismissed, actions=[
                ft.TextButton('Exportar MP4', icon=ft.Icons.MOVIE_OUTLINED, on_click=view.files.video_from_player),
                ft.TextButton('Fechar', on_click=self.close)])

    def open(self, e=None):
        if not self.view.editable() or not self.view.board.frames or self.opened or self.dismiss_pending:
            return
        self.timeline = Timeline(self.view.board, self.view.workspace.navigation.selected)
        if not self.timeline.frames:
            self.view.notify('Conecte quadros à saída deste Node Principal para reproduzir a cena.' if self.timeline.root
                else 'Selecione um Node Principal ou um quadro conectado a ele para reproduzir a cena.', 'warning')
            return
        self.popup.title = ft.Text(f'Animatic · {self.timeline.root.title or "Cena"}' if self.timeline.root else 'Animatic · Storyboard')
        self.position, self.current = 0, -1
        self.opened = True
        self.was_playing = False
        self.playing = False
        self.slider.max = self.timeline.total
        self.render(update=False)
        self.view.page.show_dialog(self.popup)

    def render(self, update=True):
        index = self.timeline.index_at(self.position)
        if index != self.current:
            self.current = index
            frame = self.timeline.frames[index]
            self.preview.set_frame(frame)
            self.subtitles.set_text(frame.subtitle if self.show_subtitles.value else '')
            self.caption.value = f'{index+1:02d} · {frame.title or "Sem título"} · {frame.duration:g} s'
        self.slider.value = self.position
        self.clock.value = f'{self.position:.1f} / {self.timeline.total:.1f} s'
        self.play.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
        self.play.tooltip = 'Pausar' if self.playing else 'Reproduzir'
        if update and self.opened and not self.view.closing:
            self.view.page.update(self.content)

    def toggle_subtitles(self, e=None):
        self.view.preferences.update(show_subtitles=bool(self.show_subtitles.value))
        if not self.opened or not self.timeline or self.current < 0:
            return
        frame = self.timeline.frames[self.current]
        self.subtitles.set_text(frame.subtitle if self.show_subtitles.value else '')
        self.view.page.update(self.content)

    def toggle(self, e=None):
        if not self.opened:
            return
        if self.playing:
            self.position = min(self.timeline.total, monotonic()-self.anchor)
            self.playing = False
        else:
            if self.position >= self.timeline.total:
                self.position = 0
            self.anchor = monotonic()-self.position
            self.playing = True
            if self.task is None or self.task.done():
                self.task = self.view.page.run_task(self.tick)
        self.render()

    def advance(self, now):
        if not self.playing:
            return
        self.position = max(0, now-self.anchor)
        if self.position >= self.timeline.total:
            if self.loop.value:
                self.position %= self.timeline.total
                self.anchor = now-self.position
            else:
                self.position = self.timeline.total
                self.playing = False
        self.render()

    async def tick(self):
        while self.opened and not self.view.closing:
            if not self.playing:
                return
            self.advance(monotonic())
            await asyncio.sleep(.05)

    def seek_start(self, e):
        self.was_playing = self.playing
        self.playing = False

    def seek(self, e):
        self.position = max(0, min(self.timeline.total, float(e.control.value)))
        self.anchor = monotonic()-self.position
        self.render()

    def seek_end(self, e):
        self.seek(e)
        if getattr(self, 'was_playing', False):
            self.toggle()
        self.was_playing = False

    def step(self, delta):
        self.playing = False
        index = max(0, min(len(self.timeline.frames)-1, self.current+delta))
        self.position = self.timeline.starts[index]
        self.render()

    def previous(self, e):
        self.step(-1)

    def next(self, e):
        self.step(1)

    def dismissed(self, e=None):
        self.subtitles.clear()
        self.dismiss_pending = False
        self.opened = self.playing = False
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def close(self, e=None):
        self.dismissed()
        self.dismiss_pending = True
        self.view.page.pop_dialog()
