"""Comandos de áudio e marcadores com histórico e recuperação do documento."""

import asyncio
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic

import flet as ft

from koma.documents.audio import AUDIO_EXTENSIONS, import_audio, load_waveform
from koma.editor.media_models import AudioTrack, TimelineMarker, next_marker_title, MAX_AUDIO_TRACKS
from koma.editor.models import MAX_CARDS, MAX_DURATION
from koma.editor.timeline_navigation import frame_position, signed_frame_position
from koma.expressions import arithmetic_value


class TimelineMedia:
    def __init__(self, player):
        self.player, self.view = player, player.view
        self.waveforms = OrderedDict()
        self.scene_waveform_limit = self.waveform_limit = 8
        self.loading = set()
        self.failed = set()
        self.cancelled = Event()
        self.task = None
        self.background = set()
        self.waveform_slots = asyncio.Semaphore(2)
        self.audio_scene = False

    @property
    def scope(self):
        return ''

    @property
    def audio_scope(self):
        return (self.player.scene_anchor or '') if self.audio_scene else ''

    def scene_offset(self, scope):
        return getattr(self.player.timeline, 'scene_offsets', {}).get(scope, 0) if scope else 0

    @property
    def track(self):
        return next((track for track in self.view.board.audio_tracks if track.scene_id == self.audio_scope), None)

    async def commit(self, board, *, pause=True, label=None, render=True):
        if not self.view.editable() or not self.player.opened:
            return
        board.validate()
        if pause:
            self.player.playing = False
        self.view.changed(board, label=label)
        self.player.rebuild_timeline()
        if render:
            self.player.render()
        await self.view.persist()

    async def pick_audio(self, e=None):
        if not self.view.editable() or self.task:
            return
        self.player.playing = False
        self.player.render()
        session, scope = self.view.session, self.audio_scope
        try:
            selected = await ft.FilePicker().pick_files(dialog_title='Importar áudio', allow_multiple=False,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=list(AUDIO_EXTENSIONS),
                initial_directory=await self.view.files.initial(purpose='audio'))
            if selected and selected[0].path and self.view.session is session and self.audio_scope == scope:
                await self.view.files.remember_directory('audio', selected[0].path)
                if self.view.session is session and self.audio_scope == scope and self.player.opened:
                    await self.import_path(selected[0].path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.view.notify(str(exc), 'error')

    async def import_path(self, source):
        if not self.view.editable() or not self.player.opened or self.task:
            return
        board, session, store, scope = self.view.board, self.view.session, self.view.store, self.audio_scope
        self.task = asyncio.current_task()
        self.cancelled.clear()
        self.view.lock(True)
        self.view.notify('Importando áudio e preparando waveform…', 'working')
        try:
            name, duration, waveform = await asyncio.to_thread(import_audio, source, store, self.cancelled.is_set)
            if (self.cancelled.is_set() or self.view.session is not session or self.view.board is not board
                    or not self.player.opened or self.audio_scope != scope):
                return
            self.remember_waveform((store.directory, name), waveform)
            track = AudioTrack(asset=name, title=Path(source).stem[:200], duration=duration, scene_id=scope)
            self.view.lock(False)
            await self.commit(replace(board, audio_tracks=tuple(item for item in board.audio_tracks if item.scene_id != scope) + (track,)))
            self.view.notify(f'Áudio importado: {track.title}', 'success')
        finally:
            self.view.lock(False)
            self.task = None

    async def load_waveform(self, track):
        store, session = self.view.store, self.view.session
        key = (store.directory, track.asset)
        task = asyncio.current_task()
        self.background.add(task)
        try:
            if self.cancelled.is_set():
                return
            async with self.waveform_slots:
                if self.cancelled.is_set():
                    return
                waveform = await asyncio.to_thread(load_waveform, store.audio / track.asset, store.waveforms, self.cancelled.is_set)
            from koma.preview_cache import PREVIEW_BUDGET_SHARES
            budget = self.view.settings.configuration.values['system']['cache'] * 1024 * 1024 / (PREVIEW_BUDGET_SHARES * self.waveform_limit)
            levels, bins = waveform.levels, waveform.bin_frames
            while len(levels) > 1 and sum(len(level) * level.itemsize for level in levels) > budget:
                levels, bins = levels[1:], bins * 2
            waveform = replace(waveform, levels=levels, bin_frames=bins)
            if self.view.session is session and not self.view.closing:
                self.remember_waveform(key, waveform)
                if self.player.opened:
                    self.player.strip.audio_lane.sync()
                    self.view.page.update(self.player.strip.audio_lane.content)
        except (OSError, ValueError, EOFError) as exc:
            if not self.cancelled.is_set():
                self.failed.add(key)
                if not self.view.closing:
                    self.view.notify(f'Waveform indisponível: {exc}', 'warning')
        finally:
            self.loading.discard(key)
            self.background.discard(task)

    def waveform(self, track):
        key = (self.view.store.directory, track.asset)
        if key in self.waveforms:
            self.waveforms.move_to_end(key)
            return self.waveforms[key]
        if key not in self.waveforms and key not in self.loading and key not in self.failed:
            self.loading.add(key)
            self.view.page.run_task(self.load_waveform, track)
        return self.waveforms.get(key)

    def remember_waveform(self, key, waveform):
        self.waveforms[key] = waveform
        self.waveforms.move_to_end(key)
        while len(self.waveforms) > self.waveform_limit:
            self.waveforms.popitem(last=False)

    async def change_track(self, **values):
        track = self.track
        if track is not None:
            updated = replace(track, **values)
            await self.commit(replace(self.view.board, audio_tracks=tuple(updated if item.id == track.id else item for item in self.view.board.audio_tracks)))

    async def set_start(self, expression):
        seconds = arithmetic_value(expression) / self.view.board.fps
        if abs(seconds) > MAX_CARDS * MAX_DURATION:
            raise ValueError('O início do áudio ultrapassa o limite da timeline.')
        await self.change_track(start=signed_frame_position(seconds, MAX_CARDS * MAX_DURATION, self.view.board.fps))

    async def remove_audio(self, e=None):
        track = self.track
        if track:
            await self.commit(replace(self.view.board, audio_tracks=tuple(item for item in self.view.board.audio_tracks if item.id != track.id)), label='Remover áudio')

    async def set_marker(self, title, expression=None, identifier=None):
        position = self.player.position if expression is None else arithmetic_value(expression) / self.view.board.fps
        if position < 0:
            raise ValueError('A posição do marcador não pode ser negativa.')
        if position > self.player.timeline.total:
            raise ValueError('O marcador precisa estar dentro da duração da cena.')
        position = frame_position(position, self.player.timeline.total, self.view.board.fps)
        marker = next((item for item in self.view.board.markers if item.id == identifier), None)
        if identifier and marker is None:
            raise ValueError('O marcador não está mais disponível.')
        updated = replace(marker, title=title.strip(), position=max(0, position - self.scene_offset(marker.scene_id))) if marker else TimelineMarker(title=title.strip(), position=position, scene_id=self.scope)
        items = tuple(updated if item.id == identifier else item for item in self.view.board.markers) if marker else (*self.view.board.markers, updated)
        await self.commit(replace(self.view.board, markers=items))

    async def add_marker(self, e=None):
        player = self.player
        if not self.view.editable() or player.editing:
            return
        position = min(player.timeline.total, monotonic() - player.anchor) if player.playing else player.position
        position = frame_position(position, player.timeline.total, self.view.board.fps)
        existing = next((marker for marker in player.timeline.markers if abs(marker.position - position) < 1e-8), None)
        player.edit_selection.claim(player.marker_editor)
        if existing:
            player.marker_editor.selected = existing.id
            player.render()
            player.focus_timeline()
            return
        marker = TimelineMarker(title=next_marker_title(player.timeline.markers),
            position=position, scene_id=self.scope)
        player.marker_editor.selected = marker.id
        await self.commit(replace(self.view.board, markers=(*self.view.board.markers, marker)), pause=False)
        player.focus_timeline()

    async def rename_marker(self, identifier, title, board, session):
        if self.view.board is not board or self.view.session is not session:
            raise ValueError('O projeto mudou. Selecione o marcador novamente.')
        marker = next((item for item in board.markers if item.id == identifier), None)
        if marker is None:
            raise ValueError('Marcador indisponível.')
        updated = replace(marker, title=title.strip())
        await self.commit(replace(board, markers=tuple(updated if item.id == identifier else item for item in board.markers)))

    async def remove_marker(self, identifier):
        await self.commit(replace(self.view.board, markers=tuple(marker for marker in self.view.board.markers if marker.id != identifier)))

    def jump_marker(self, delta):
        markers = self.player.timeline.markers
        if delta > 0:
            target = next((marker for marker in markers if marker.position > self.player.position + 1e-8), None)
        else:
            target = next((marker for marker in reversed(markers) if marker.position < self.player.position - 1e-8), None)
        if target:
            self.player.strip.navigator.seek(target.position)

    async def shutdown(self):
        self.cancelled.set()
        if self.task and self.task is not asyncio.current_task():
            await asyncio.shield(self.task)
        pending = tuple(task for task in self.background if task is not asyncio.current_task())
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
