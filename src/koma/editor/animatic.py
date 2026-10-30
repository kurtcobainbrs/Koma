"""Playback and editing tools shared by the full Animatic workspace."""

import asyncio
from time import monotonic

import flet as ft
from koma.ui.event_updates import explicit_updates

from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT, ICON_SIZE, MUTED, input_style
from koma.ui.typography import FONT_HEADING, TEXT_SECTION, TEXT_SMALL
from koma.editor.framing import ImageViewport
from koma.editor.subtitle_preview import SubtitlePreview
from koma.editor.timeline import Timeline
from koma.editor.scenes import resolve_scene
from koma.editor.timeline_edit import TimelineEditor
from koma.editor.shortcuts import Action
from koma.keymap import key_name
from koma.ui.timeline_strip import TimelineStrip
from koma.ui.animatic_workspace import AnimaticWorkspace
from koma.editor.selection import NodeSelection
from koma.ui.player_toolbar import PlayerToolbar
from koma.ui.components import toggle_icon
from koma.editor.timeline_media import TimelineMedia
from koma.audio_transport import AudioTransport
from koma.editor.marker_edit import MarkerEditor
from koma.editor.timeline_navigation import adjacent_stop
from koma.editor.drawing_editor import FrameDrawingEditor
from koma.ui.drawing_surface import DrawingSurface
from koma.editor.video_preview import VideoPreview
from koma.editor.time_display import clock_text
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.retained_container import retain_children
from koma.ui.reference_presentation import ReferencePresentation


class AnimaticPlayer:
    def __init__(self, view):
        self.view = view
        self.opened = self.playing = False
        self.suspended = False
        self.selection = NodeSelection()
        self.inspector_key = None
        self.position = 0.0
        self.anchor = 0.0
        self.current = -1
        self.modifiers = set()
        self.task = None
        self.timeline = None
        self.scene_anchor = None
        self.media = TimelineMedia(self)
        self.audio_transport = AudioTransport()
        self.video_preview = VideoPreview(self)
        self.duration_editor = TimelineEditor(self)
        self.marker_editor = MarkerEditor(self)
        self.drawing = FrameDrawingEditor(self)
        self.drawing_surface = DrawingSurface(self)
        self.strip = TimelineStrip(self, self.duration_editor)
        self.preview = ImageViewport(view, height=400, show_drawing=False)
        self.reference_presentation = ReferencePresentation(self)
        self.subtitles = SubtitlePreview(self)
        self.screen = ft.Container(aspect_ratio=view.board.frame_format.aspect_ratio, content=ft.Stack(
            [self.preview.content, self.drawing_surface.content, self.subtitles.content,
                self.reference_presentation.preview.content], fit=ft.StackFit.EXPAND))
        self.caption = ft.Text(size=TEXT_SMALL, font_family=FONT_HEADING, max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS)
        self.clock = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.play = ft.IconButton(icon=ft.Icons.PLAY_ARROW, tooltip='Reproduzir', on_click=self.toggle,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.loop = toggle_icon(ft.Icons.REPEAT, ft.Icons.REPEAT_ON, self.toggle_loop)
        self.show_subtitles = toggle_icon(ft.Icons.SUBTITLES_OFF_OUTLINED, ft.Icons.SUBTITLES,
            self.toggle_subtitles, selected=True)
        self.previous_button = ft.IconButton(icon=ft.Icons.SKIP_PREVIOUS, on_click=self.previous,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.next_button = ft.IconButton(icon=ft.Icons.SKIP_NEXT, on_click=self.next,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        transport = ft.Row([self.previous_button, self.play, self.next_button], spacing=0, tight=True)
        self.toolbar = PlayerToolbar(self.strip.duration_input.field, transport, self.clock,
            self.strip.fps, self.strip.history_tools, self.strip.zoom_tools,
            [self.show_subtitles, self.loop], self.strip.audio_controls.tools)
        # Reuse the audio footer for frame context instead of adding another band.
        self.strip.footer_context.content = self.caption
        self.controls = self.toolbar.commands
        self.preview_bounds = None
        self.preview_slot = ft.Container(content=self.screen, alignment=ft.Alignment.CENTER,
            on_size_change=self.preview_resized)
        self.export_button = ft.OutlinedButton('Exportar MP4', icon=ft.Icons.FILE_UPLOAD_OUTLINED, tooltip='Exportar animatic em MP4',
            height=COMPACT_CONTROL_HEIGHT, on_click=view.files.video_from_player)
        self.title = ft.Text('Animatic', width=WORKSPACE_STYLE.scene_choice_width, size=TEXT_SECTION,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.scene_choice = ft.Dropdown(width=WORKSPACE_STYLE.scene_choice_width, options=[], on_select=self.choose_scene,
            tooltip='Cena', **input_style(height=COMPACT_CONTROL_HEIGHT))
        self.scenes_key = None
        self.close_button = ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip='Voltar ao canvas · Esc', on_click=self.close,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=ICON_SIZE)
        self.drawing_slot = ft.Container(content=self.drawing_surface.tools, expand=True)
        self.header = ft.Row([
                self.scene_choice, self.title, self.drawing_slot,
                ft.IconButton(icon=ft.Icons.PERM_MEDIA_OUTLINED, tooltip='Mídias do quadro',
                    width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT,
                    on_click=lambda e: self.view.node_media.open_editor(self.selection.active)
                        if self.selection.active else None),
                ft.IconButton(icon=ft.Icons.INFO_OUTLINED, tooltip='Dados de referência',
                    width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT,
                    on_click=self.reference_presentation.open_fields),
                    self.export_button], spacing=APP_PADDING * 2)
        self.layout = AnimaticWorkspace(self, self.header)
        self.content, self.surface = self.layout.body, self.layout.content

    def open(self, e=None):
        if not self.view.editable() or not self.view.board.frames or self.opened:
            return
        if not self.view.settings.configuration.values['drawing']['remember']:
            self.drawing.set_tool('select')
        previous = self.timeline
        active = self.view.workspace.navigation.selected
        scene = resolve_scene(self.view.board, active, fallback=self.scene_anchor)
        reusable = (previous is not None and previous.board is self.view.board
            and (previous.root.id if previous.root else None) == (scene.id if scene else None))
        self.timeline = previous if reusable else Timeline(self.view.board, scene.id if scene else active)
        self.title.value = self.timeline.root.title or 'Cena' if self.timeline.root else 'Prévia'
        self.scene_anchor = self.timeline.root.id if self.timeline.root else None
        same_scope = previous is not None and (previous.root.id if previous.root else None) == self.scene_anchor
        self.position = max(0, min(self.position, self.timeline.total)) if same_scope else 0
        active_index = next((index for index, frame in enumerate(self.timeline.frames) if frame.id == active), None)
        if active_index is not None:
            self.position = self.timeline.starts[active_index]
        if not reusable:
            self.current = -1
        self.view.properties.end_adjust()
        self.view.workspace.cancel_gestures()
        self.opened = True
        self.suspended = False
        identifiers = {frame.id for frame in self.timeline.frames}
        selected = active if active in identifiers else self.selection.active
        selected = selected if selected in identifiers else (self.timeline.frames[0].id
            if self.timeline.frames else self.scene_anchor)
        self.selection.replace({selected} if selected else set(), selected)
        self.inspector_key = None
        self.media.cancelled.clear()
        self.playing = False
        if same_scope:
            self.strip.sync()
        else:
            self.strip.reset()
        self.render(update=False)
        self.view.work_modes.show(True, retain_timeline=reusable)
        self.focus_timeline()

    def focus_timeline(self):
        self.view.focus.request(self.keyboard,
            lambda: self.opened and self.view.active and not self.view.closing)

    def sync_scenes(self):
        scenes = tuple((frame.id, self.view.production.label(frame.id)) for frame in self.view.board.frames if frame.node_type.starts_scene)
        if scenes != self.scenes_key:
            self.scenes_key = scenes
            self.scene_choice.options = [ft.DropdownOption(identifier, title) for identifier, title in scenes]
        self.scene_choice.visible = bool(scenes)
        self.title.visible = not bool(scenes)
        self.scene_choice.value = self.scene_anchor
        self.scene_choice.disabled = self.editing or not self.view.editable()
        self.title.value = 'Animatic' if scenes else self.view.board.title

    def choose_scene(self, e=None):
        identifier = self.scene_choice.value
        if not self.view.editable() or self.editing or not any(
                frame.id == identifier and frame.node_type.starts_scene for frame in self.view.board.frames):
            return
        self.playing = False
        self.audio_transport.stop()
        self.video_preview.clear()
        self.drawing.clear_selection()
        self.view.properties.release_field_focus()
        self.timeline = Timeline(self.view.board, identifier)
        self.scene_anchor, self.position, self.current = identifier, 0, -1
        self.selection.replace({self.timeline.frames[0].id} if self.timeline.frames else {identifier})
        self.strip.reset()
        self.render()
        self.focus_timeline()

    def suspend(self):
        if self.opened:
            self.drawing_surface.close_picker()
            self.dismissed()
            self.suspended = True

    def resume(self):
        if not self.suspended or not self.view.editable():
            return
        self.suspended = False
        self.opened = True
        self.media.cancelled.clear()
        self.rebuild_timeline()
        self.render(update=False)
        self.view.work_modes.show(True)
        self.focus_timeline()

    def fit_preview(self):
        self.screen.aspect_ratio = self.view.board.frame_format.aspect_ratio
        if self.preview_bounds:
            self.screen.width, self.screen.height = self.view.board.frame_format.fit(*self.preview_bounds)

    @property
    def presenting(self):
        return self.opened and self.view.active and not self.view.closing

    @explicit_updates
    def preview_resized(self, e):
        if not self.presenting:
            return
        if e.width > 0 and e.height > 0 and self.preview_bounds != (e.width, e.height):
            self.preview_bounds = (e.width, e.height)
            self.fit_preview()
            if self.timeline:
                self.reference_presentation.sync()
            if self.opened:
                self.view.page.update(self.screen)

    def rebuild_timeline(self):
        self.timeline = Timeline(self.view.board, self.scene_anchor)
        self.position = max(0, min(self.position, self.timeline.total))
        self.current = -1

    def select_node(self, identifier, *, seek=False):
        if not self.opened or self.editing or not self.view.editable():
            return
        if not any(frame.id == identifier for frame in self.view.board.frames):
            return
        if self.selection.active == identifier and not seek:
            self.focus_timeline()
            return
        self.selection.replace({identifier}, identifier)
        self.sync_inspector()
        controls = self.strip.sync_selection()
        if controls:
            self.view.page.update(*controls)
        if seek:
            index = next((i for i, frame in enumerate(self.timeline.frames) if frame.id == identifier), None)
            if index is not None:
                self.playing = False
                self.position = self.timeline.starts[index]
        self.render_position()
        self.focus_timeline()

    def sync_inspector(self, *, update=True):
        if not self.opened:
            return
        previous = self.selection.active
        identifiers = {frame.id for frame in self.view.board.frames}
        self.selection.replace(self.selection.ids & identifiers)
        if not self.selection.ids and self.timeline and self.timeline.frames:
            self.selection.replace({self.timeline.frames[0].id})
        if previous != self.selection.active:
            controls = self.strip.sync_selection()
            if controls and self.view.active and not self.view.closing:
                self.view.page.update(*controls)
        frame = next((frame for frame in self.view.board.frames if frame.id == self.selection.active), None)
        key = (self.selection.active, id(frame), self.view.busy, self.editing)
        if key == self.inspector_key or self.view.workspace.navigation.editing_fields:
            return
        self.inspector_key = key
        self.view.properties.sync()
        if update and self.view.active and not self.view.closing:
            self.view.page.update(self.view.properties.content)

    def document_changed(self):
        if self.opened and not self.editing and self.timeline.board is not self.view.board:
            self.timeline = self.timeline.with_board(self.view.board)
            self.position = max(0, min(self.position, self.timeline.total))
            self.current = -1
            self.render()

    @property
    def editing(self):
        return bool(self.duration_editor.drag or self.duration_editor.committing
            or self.marker_editor.drag or self.marker_editor.committing
            or self.drawing.drag or self.drawing.committing
            or self.strip.audio_lane.drag.snapshot or self.strip.audio_controls.gain.snapshot)

    def render(self, update=True):
        if self.timeline is None:
            return
        self.fit_preview()
        self.sync_scenes()
        if self.duration_editor.drag is None and self.timeline.board is not self.view.board:
            self.rebuild_timeline()
        if self.drawing.drag and (not self.timeline.frames or
                self.timeline.frames[self.timeline.index_at(self.position)].id != self.drawing.drag.frame.id):
            self.drawing.cancel(update=False)
        editing = self.editing
        self.play.disabled = editing or not self.timeline.frames
        self.export_button.disabled = editing or not self.view.editable() or not self.timeline.frames
        self.preview.content.visible = bool(self.timeline.frames)
        if not self.timeline.frames:
            self.playing = False
            self.current = -1
            self.subtitles.set_text('')
            self.caption.value = 'Nenhum quadro ativo nesta cena.'
            self.caption.tooltip = None
            self.position = 0
        index = self.timeline.index_at(self.position)
        if self.timeline.frames and index != self.current:
            self.current = index
            frame = self.timeline.frames[index]
            self.preview.set_frame(frame)
            self.subtitles.set_text(frame.subtitle if self.show_subtitles.selected else '')
            self.caption.value = f'{index+1:02d} · {frame.title or "Sem título"}'
            self.caption.tooltip = f'{frame.duration * self.view.board.fps:.6g} f · {frame.duration:.6g} s'
        self.clock.value = clock_text(self.position, self.timeline.total, self.view.board.fps, self.view.settings.configuration.values['timeline'])
        self.play.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
        self.play.tooltip = self.view.keymap.describe('Pausar' if self.playing else 'Reproduzir', Action.PLAY)
        self.previous_button.tooltip = self.view.keymap.describe('Quadro ou marcador anterior', Action.PREVIOUS_STOP)
        self.next_button.tooltip = self.view.keymap.describe('Próximo quadro ou marcador', Action.NEXT_STOP)
        self.show_subtitles.tooltip = ('Legendas ligadas · clique para ocultar' if self.show_subtitles.selected
            else 'Legendas desligadas · clique para mostrar')
        self.loop.tooltip = 'Repetir ligado · clique para desligar' if self.loop.selected else 'Repetir desligado · clique para ligar'
        self.previous_button.disabled = self.next_button.disabled = editing or not self.timeline.frames
        self.strip.sync()
        self.sync_inspector(update=update)
        self.drawing_surface.sync()
        self.sync_video()
        self.audio_transport.update(self.timeline, self.view.store, self.playing and self.opened, self.position)
        if self.audio_transport.error:
            self.view.notify(self.audio_transport.error, 'warning')
            self.audio_transport.error = ''
        if update and self.opened and not self.view.closing:
            self.view.chrome.sync()
            self.view.page.update(self.content, self.layout.timeline, self.view.chrome.content)

    def render_duration_preview(self, frame):
        """Update timing controls without resending the large preview or canvas."""
        self.play.disabled = self.previous_button.disabled = self.next_button.disabled = self.editing
        self.export_button.disabled = self.editing or not self.view.editable()
        self.caption.tooltip = f'{frame.duration * self.view.board.fps:.6g} f · {frame.duration:.6g} s'
        self.clock.value = clock_text(self.position, self.timeline.total, self.view.board.fps, self.view.settings.configuration.values['timeline'])
        self.strip.sync()
        if self.opened and not self.view.closing:
            with retain_children(self.strip.audio_lane.canvas,
                    *(block.thumbnail.canvas for block in self.strip.blocks.values())):
                self.view.page.update(self.strip.content, self.controls, self.caption, self.export_button,
                    self.reference_presentation.preview.content)

    def set_gesture_locked(self, locked):
        """Publish a logical gesture lock without touching preview or tracks."""
        self.controls.disabled = locked
        self.scene_choice.disabled = locked or not self.view.editable()
        self.export_button.disabled = locked or not self.view.editable() or not self.timeline.frames
        self.play.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
        if self.presenting:
            self.view.page.update(self.controls, self.scene_choice, self.export_button)

    def pause_for_edit(self):
        self.playing = False
        self.audio_transport.stop()

    def render_position(self):
        """Seek/playback update only transport and the frames that actually change."""
        if not self.opened or self.view.closing or self.timeline is None:
            return
        if self.timeline.board is not self.view.board or self.current < 0:
            self.render()
            return
        old_index = self.current
        index = self.timeline.index_at(self.position)
        if index != old_index:
            self.render(update=False)
            controls = [self.preview.content, self.subtitles.content, self.caption,
                self.drawing_surface.content, self.drawing_surface.visibility,
                self.strip.duration_input.field,
                *[self.strip.blocks[self.timeline.frames[i].id].box
                    for i in {old_index, index} if 0 <= i < len(self.timeline.frames)]]
        else:
            self.strip.sync_cursor()
            self.sync_video()
            self.clock.value = clock_text(self.position, self.timeline.total, self.view.board.fps, self.view.settings.configuration.values['timeline'])
            self.play.icon = ft.Icons.PAUSE if self.playing else ft.Icons.PLAY_ARROW
            self.play.tooltip = self.view.keymap.describe('Pausar' if self.playing else 'Reproduzir', Action.PLAY)
            self.audio_transport.update(self.timeline, self.view.store, self.playing, self.position)
            controls = []
        reference_controls = self.reference_presentation.sync_current()
        self.view.page.update(self.clock, self.play, self.strip.playhead, self.strip.needle, *controls, *reference_controls)

    def sync_video(self):
        if self.timeline and 0 <= self.current < len(self.timeline.frames):
            self.video_preview.request(self.timeline.frames[self.current],
                self.position - self.timeline.starts[self.current])
        else:
            self.video_preview.clear()

    def toggle_subtitles(self, e=None):
        self.show_subtitles.selected = not self.show_subtitles.selected
        self.view.preferences.update(show_subtitles=bool(self.show_subtitles.selected))
        if not self.opened or not self.timeline or self.current < 0:
            return
        frame = self.timeline.frames[self.current]
        self.subtitles.set_text(frame.subtitle if self.show_subtitles.selected else '')
        self.render()
        self.focus_timeline()

    def toggle_loop(self, e=None):
        self.loop.selected = not self.loop.selected
        self.render()
        self.focus_timeline()

    def toggle(self, e=None):
        if not self.opened or self.play.disabled:
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
        self.focus_timeline()

    def advance(self, now):
        if not self.playing:
            return
        self.position = max(0, now-self.anchor)
        if self.position >= self.timeline.total:
            if self.loop.selected:
                self.position %= self.timeline.total
                self.anchor = now-self.position
            else:
                self.position = self.timeline.total
                self.playing = False
        self.render_position()

    async def tick(self):
        while self.opened and not self.view.closing:
            if not self.playing:
                return
            self.advance(monotonic())
            await asyncio.sleep(.05)

    def step(self, delta):
        if not self.timeline.frames or self.editing:
            return
        self.playing = False
        self.position = adjacent_stop(self.timeline, self.position, delta)
        self.render()

    def frame_step(self, delta):
        self.strip.navigator.seek(self.position + delta / self.view.board.fps)

    def previous(self, e):
        self.step(-1)
        self.focus_timeline()

    @explicit_updates
    def key_up(self, e):
        self.modifiers.discard(key_name(e.key))

    @explicit_updates
    async def key_down(self, e):
        modifiers = {name for field, name in (('ctrl', 'Ctrl'), ('alt', 'Alt'),
            ('shift', 'Shift'), ('meta', 'Meta')) if getattr(e, field, False)}
        self.modifiers = modifiers
        if key_name(e.key) in ('Ctrl', 'Alt', 'Shift', 'Meta'):
            self.modifiers.add(key_name(e.key))
        action = self.view.keymap.resolve(e.key, modifiers, 'timeline')
        if self.view.workspace.navigation.editing_fields:
            if action == Action.CANCEL:
                self.view.properties.release_field_focus()
                self.inspector_key = None
                self.sync_inspector()
                self.focus_timeline()
            return
        if self.drawing_surface.picker is not None:
            if action == Action.CANCEL:
                self.drawing_surface.close_picker()
                self.focus_timeline()
            elif key_name(e.key) == 'Enter':
                self.drawing_surface.picker.apply(e)
                self.focus_timeline()
            return
        if self.drawing_surface.focused:
            if action == Action.CANCEL:
                self.drawing_surface.set_width()
                self.focus_timeline()
            return
        if self.strip.marker_lane.renaming is not None:
            if action == Action.CANCEL:
                self.strip.marker_lane.cancel_rename()
                self.focus_timeline()
            return
        if self.strip.audio_controls.focused:
            if action == Action.CANCEL:
                self.strip.audio_controls.blur()
                self.focus_timeline()
            return
        if self.strip.duration_input.focused:
            if action == Action.CANCEL:
                self.strip.duration_input.cancel()
                self.focus_timeline()
            return
        if self.drawing_surface.tool_menu.opened:
            if action in (Action.DRAWING_TOOLS, Action.CANCEL):
                self.drawing_surface.tool_menu.close()
            return
        if action == Action.CANCEL:
            if not self.editing and self.drawing.selected_index() is not None:
                self.drawing.clear_selection()
                self.render()
                self.focus_timeline()
                return
            editing = self.editing
            self.drawing.cancel()
            self.strip.audio_lane.drag.cancel()
            self.strip.audio_controls.gain.cancel()
            self.duration_editor.cancel()
            self.marker_editor.cancel()
            if editing:
                self.focus_timeline()
            else:
                self.close()
            return
        if self.editing or not self.view.editable():
            return
        if action == Action.DRAWING_TOOLS:
            await self.drawing_surface.toggle_tools()
        elif action == Action.PROPERTIES:
            self.view.properties.toggle()
        elif action == Action.PLAY:
            self.toggle()
        elif action == Action.ADD_MARKER:
            await self.media.add_marker()
        elif action == Action.SNAP:
            self.strip.audio_controls.toggle_snap()
        elif action == Action.PREVIOUS_STOP:
            self.step(-1)
        elif action == Action.NEXT_STOP:
            self.step(1)
        elif action == Action.PREVIOUS_FRAME:
            self.frame_step(-1)
        elif action == Action.NEXT_FRAME:
            self.frame_step(1)
        elif action == Action.START:
            self.strip.navigator.seek(0)
        elif action == Action.END:
            self.strip.navigator.seek(self.timeline.total)
        elif action == Action.RENAME_MARKER:
            self.strip.marker_lane.rename()
        elif action == Action.DELETE_SELECTION:
            await self.delete_selection()
        elif action == Action.IMPORT_AUDIO:
            await self.media.pick_audio()
        elif action == Action.UNDO:
            await self.strip.undo_edit()
        elif action == Action.REDO:
            await self.strip.redo_edit()
        elif action in (Action.FOCUS, Action.FIT):
            self.strip.fit()

    async def delete_selection(self):
        if self.editing or not self.view.editable():
            return
        if await self.drawing.delete_selected():
            return
        if self.marker_editor.selected:
            await self.media.remove_marker(self.marker_editor.selected)

    def next(self, e):
        self.step(1)
        self.focus_timeline()

    def dismissed(self, e=None):
        self.opened = False
        self.modifiers.clear()
        self.video_preview.clear()
        self.drawing_surface.tool_menu.close()
        self.drawing.cancel(update=False)
        self.drawing.clear_selection()
        self.drawing_surface.reset_inputs()
        self.drawing_surface.focused = False
        self.strip.audio_lane.drag.cancel(update=False)
        self.strip.audio_controls.gain.cancel(update=False)
        self.media.cancelled.set()
        self.audio_transport.stop()
        self.strip.audio_controls.focused = False
        self.marker_editor.cancel(update=False)
        self.marker_editor.selected = None
        self.strip.marker_lane.cancel_rename()
        self.strip.navigator.end()
        self.strip.duration_input.cancel()
        self.duration_editor.cancel(update=False)
        self.opened = self.playing = False
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def close(self, e=None):
        if not self.opened and not self.suspended:
            return
        self.suspended = False
        self.drawing_surface.close_picker()
        self.drawing_surface.tool_menu.close()
        self.dismissed()
        self.view.work_modes.show(False)
        self.view.focus_editor()
