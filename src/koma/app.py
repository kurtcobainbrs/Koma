"""Janela desktop com documentos independentes em abas de documentos."""

import argparse
import asyncio
from dataclasses import replace
from pathlib import Path

import flet as ft
from koma.ui.event_updates import explicit_updates

from koma.documents.session import DocumentSession
from koma.editor.view import StoryboardView
from koma.editor.models import Storyboard
from koma.paths import data_directory
from koma.preferences import AppPreferences
from koma.ui.design import APP_PADDING, BACKGROUND, app_theme
from koma.ui.typography import register_fonts
from koma.ui.project_tabs import ProjectTabs
from koma.ui.project_drop import ProjectDrop
from koma.documents.recent import RecentDocuments
from koma.editor.node_clipboard import NodeClipboard
from koma.editor.document_tools import DocumentTools
from koma.ui.retained_container import RetainedColumn, retain_children


class KomaApplication:
    def __init__(self, page, directory, document=None):
        self.page = page
        self.page.title = 'Koma App'
        self.settings = AppPreferences(directory)
        self.page.theme = app_theme(accent=self.settings.configuration.values['appearance']['accent'])
        self.page.theme_animation_style = ft.AnimationStyle.no_animation()
        self.recent = RecentDocuments(directory, limit=self.settings.configuration.values['files']['recent'])
        self.settings.configuration.listeners.append(self.preferences_changed)
        self.node_clipboard = NodeClipboard()
        self.document_tools = DocumentTools(self)
        self.closing_attempt = self.transitioning = False
        self.views = []
        self.untitled_number = 0
        self.view = self.make_view(DocumentSession(directory))
        self.views.append(self.view)
        self.menu_host = ft.Container(content=self.view.chrome.content)
        self.editor_host = ft.Container(content=self.view.content, expand=True)
        self.tabs = ProjectTabs(self)
        self.host = RetainedColumn(hold_updates=lambda: False,
            controls=[self.menu_host, self.tabs.content, self.editor_host], expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.project_drop = ProjectDrop(self)
        self.surface = self.project_drop.surface(self.host)
        self.document = document

    def make_view(self, session):
        if session.path is None and session.recovered_from is None and session.board == Storyboard():
            self.untitled_number += 1
            from koma.editor.frame_format import FrameFormat
            initial = self.settings.configuration.values['projects']
            session.board = session.saved_board = replace(session.board, title=f'Projeto {self.untitled_number}',
                fps=initial['fps'], frame_format=FrameFormat(initial['width'], initial['height']))
        view = StoryboardView(self.page, session, self.settings,
            on_session=self.switch_session, on_state=self.editor_changed)
        view.content.controls.remove(view.chrome.content)
        view.can_save_to = lambda path: self.can_save_to(view, path)
        view.can_accept_drop = lambda: self.view is view and not self.transitioning and not self.closing_attempt
        view.open_project_path = self.open_project
        view.document_tools = self.document_tools
        view.node_clipboard = self.node_clipboard
        view.document_saved = self.recent.add
        async def close_project():
            await self.close_tab(view)
        view.close_project = close_project
        return view

    def preferences_changed(self, previous, current):
        if previous['appearance']['accent'] != current['appearance']['accent']:
            self.page.theme = app_theme(accent=current['appearance']['accent'])
            # Inherited theme colors repaint natively; no Python traversal of
            # stable cards, image sources, waveform or timeline is needed.
            with retain_children(self.host):
                self.page.update()
        self.recent.limit = current['files']['recent']
        self.recent.paths = self.recent.paths[:self.recent.limit]

    async def open_project(self, path):
        if self.transitioning or self.closing_attempt or any(view.busy for view in self.views):
            return
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() != '.koma':
            raise ValueError('Escolha um arquivo .koma.')
        existing = next((view for view in self.views if view.session.path is not None
            and view.session.path.resolve() == path), None)
        if existing is not None:
            await self.select_view(existing)
        else:
            await self.view.files.change_document(path=path)

    def editor_changed(self, view):
        drop_changed = hasattr(self, 'project_drop') and self.project_drop.sync()
        if hasattr(self, 'tabs') and view in self.views:
            if drop_changed:
                with retain_children(self.host):
                    self.page.update(self.project_drop.control)
            if self.tabs.sync() and not self.closing_attempt:
                self.page.update(self.tabs.content)

    def can_save_to(self, view, path):
        return not any(other is not view and other.session.path is not None
            and other.session.path.resolve() == Path(path).resolve() for other in self.views)

    def set_transition(self, value):
        self.transitioning = value
        # Pointer gating must not change inherited widget enabled states.
        # Retained descendants do not rebuild when only an ancestor unlocks.
        self.editor_host.ignore_interactions = self.menu_host.ignore_interactions = value
        self.tabs.sync()
        self.project_drop.sync()
        controls = [self.editor_host, self.menu_host, self.tabs.content]
        if self.project_drop.control is not None:
            controls.append(self.project_drop.control)
        with retain_children(self.view.content, self.host):
            self.page.update(*controls)

    def move_tab(self, source, target=None):
        if (self.transitioning or self.closing_attempt or any(v.busy for v in self.views)
                or source not in self.views or (target is not None and target not in self.views)
                or source is target):
            return False
        index = self.views.index(target) if target is not None else len(self.views) - 1
        self.views.remove(source)
        self.views.insert(index, source)
        self.tabs.sync()
        self.page.update(self.tabs.content)
        return True

    async def start(self):
        await self.view.activate()
        if not self.document and self.settings.configuration.values['system']['restore']:
            from koma.session_preferences import read_session
            paths = await asyncio.to_thread(read_session, self.settings.directory)
            for path in paths:
                try:
                    await self.open_project(path)
                except (OSError, ValueError):
                    self.view.notify('Um projeto da última sessão não pôde ser aberto.', 'warning')
        if self.document:
            try:
                session = await asyncio.to_thread(DocumentSession.open, self.document, self.settings.directory)
                await self.switch_session(session)
            except (OSError, ValueError) as exc:
                self.view.notify(f'Não foi possível abrir: {exc}', 'error')
        if await asyncio.to_thread(DocumentSession.recoveries, self.settings.directory):
            self.view.notify('Há sessões anteriores disponíveis em Arquivo → Recuperar sessão.', 'warning')
        else:
            from koma.ui import drop_runtime
            if not drop_runtime.enabled():
                self.view.notify(drop_runtime.unavailable_reason(), 'warning')

    def disconnected(self, e=None):
        for view in self.views:
            view.focus.disconnect()

    def reconnected(self, e=None):
        for view in self.views:
            view.focus.reconnect()
        self.view.focus_editor()

    async def select_view(self, target):
        if target not in self.views or self.transitioning or self.closing_attempt or any(v.busy for v in self.views):
            return False
        if target is self.view:
            return True
        self.set_transition(True)
        try:
            await self.show_view(target)
            return True
        except (OSError, ValueError, RuntimeError) as exc:
            self.view.notify(f'Não foi possível ativar o projeto: {exc}', 'error')
            return False
        finally:
            self.set_transition(False)

    async def show_view(self, target):
        old = self.view
        await old.deactivate()
        self.view = target
        self.project_drop.sync()
        target.active = True
        self.menu_host.content = target.chrome.content
        self.editor_host.content = target.content
        self.tabs.sync()
        self.page.update(self.host)
        try:
            await target.activate()
            if target.session.path:
                self.recent.add(target.session.path)
            if target.load_error:
                raise ValueError(target.load_error)
        except Exception:
            target.active = False
            self.view, old.active = old, True
            self.menu_host.content = old.chrome.content
            self.editor_host.content = old.content
            self.tabs.sync()
            self.page.update(self.host)
            self.page.run_task(old.workspace.resume)
            raise

    async def switch_session(self, session):
        """Uma sessão aberta vira uma aba, sem substituir o documento anterior."""
        if self.transitioning or self.closing_attempt:
            raise RuntimeError('Aguarde a operação atual terminar.')
        existing = next((v for v in self.views if session.path is not None and session.recovered_from is None
            and v.session.path is not None and v.session.path.resolve() == session.path.resolve()), None)
        self.set_transition(True)
        candidate = None
        try:
            if existing is not None:
                await asyncio.to_thread(session.close)
                if existing is not self.view:
                    await self.show_view(existing)
                return
            candidate = self.make_view(session)
            self.views.append(candidate)
            await self.show_view(candidate)
        except Exception:
            if candidate is not None:
                self.views.remove(candidate)
                candidate.closing = True
                await candidate.shutdown()
                await asyncio.to_thread(candidate.session.close)
            raise
        finally:
            self.set_transition(False)

    async def new_document(self, e=None):
        if not self.transitioning and not self.closing_attempt:
            await self.view.files.new_document()

    async def close_tab(self, target):
        if target not in self.views or self.transitioning or self.closing_attempt or any(v.busy for v in self.views):
            return False
        self.set_transition(True)
        target.lock(True)
        try:
            if not await target.files.guard_changes():
                return False
            was_active = target is self.view
            if was_active:
                await target.deactivate()
            # As views inativas não devem publicar controles fora da árvore da página.
            target.closing = True
            await target.shutdown()
            index = self.views.index(target)
            self.views.remove(target)
            await asyncio.to_thread(target.session.close, resolved=True)
            if was_active:
                if not self.views:
                    self.views.append(self.make_view(DocumentSession(self.settings.directory)))
                self.view = self.views[min(index, len(self.views) - 1)]
                self.view.active = True
                self.menu_host.content = self.view.chrome.content
                self.editor_host.content = self.view.content
                self.page.update(self.menu_host, self.editor_host)
                await self.view.activate()
            return True
        except (OSError, ValueError, RuntimeError) as exc:
            target.closing = False
            if target.shortcuts_changed not in target.keymap.listeners:
                target.keymap.listeners.append(target.shortcuts_changed)
            if target is self.view:
                target.active = True
            self.view.notify(f'Não foi possível fechar o projeto: {exc}', 'error')
            return False
        finally:
            if target in self.views:
                target.lock(False)
            self.set_transition(False)

    async def close(self):
        if self.closing_attempt or self.transitioning or self.view.closing:
            return False
        if any(view.busy for view in self.views):
            self.view.notify('Aguarde a operação terminar ou cancele a exportação antes de fechar.', 'warning')
            return False
        self.closing_attempt = True
        for view in self.views:
            view.focus.suspend()
            view.lock(True)
        self.tabs.sync()
        self.page.update(self.tabs.content)
        try:
            # Nenhuma aba é descartada até todas as confirmações terminarem.
            for view in self.views:
                if not await view.files.guard_changes():
                    return False
            from koma.session_preferences import write_session
            await asyncio.to_thread(write_session, self.settings.directory, [view.session.path for view in self.views])
            for view in self.views:
                view.closing = True
                await view.shutdown()
            for view in self.views:
                await asyncio.to_thread(view.session.close, resolved=True)
            await self.page.window.destroy()
            return True
        except (OSError, ValueError, RuntimeError) as exc:
            for view in self.views:
                view.closing = False
                if view.shortcuts_changed not in view.keymap.listeners:
                    view.keymap.listeners.append(view.shortcuts_changed)
            self.view.notify(f'Não foi possível fechar com segurança: {exc}', 'error')
            return False
        finally:
            self.closing_attempt = False
            for view in self.views:
                if not view.closing:
                    view.focus.resume()
                    view.lock(False)
            self.tabs.sync()
            if not self.view.closing:
                self.page.update(self.tabs.content)


def mount(page, document=None):
    page.title = 'Koma App'
    register_fonts(page)
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BACKGROUND
    page.padding = APP_PADDING
    page.window.width, page.window.height = 1180, 800
    page.window.min_width, page.window.min_height = 600, 600
    page.window.prevent_close = True
    application = KomaApplication(page, data_directory(), document)
    page.on_disconnect = application.disconnected
    page.on_connect = application.reconnected
    @explicit_updates
    async def on_window_event(e):
        if e.type == ft.WindowEventType.CLOSE:
            await application.close()
        elif e.type == ft.WindowEventType.BLUR:
            for view in application.views:
                view.player.duration_editor.cancel()
                view.player.drawing.cancel(update=view.active)
                view.player.strip.audio_lane.drag.cancel(update=view.active)
                view.player.marker_editor.cancel()
                view.player.strip.navigator.end()
                nav = view.workspace.navigation
                view.workspace.secondary_pointer.cancel(update=False)
                nav.reset_keys()
                if view.workspace.drag:
                    view.workspace.cancel_drag(view.workspace.drag.identifier)
                nav.sync(update=view.active)
    page.window.on_event = on_window_event
    @explicit_updates
    async def on_keyboard_event(e):
        from koma.editor.application_commands import dispatch
        if await dispatch(application, e):
            return
        player = application.view.player
        if player.opened:
            await player.key_down(e)
    page.on_keyboard_event = on_keyboard_event
    page.add(application.surface)
    page.run_task(application.start)
    return application


def main():
    parser = argparse.ArgumentParser(description='Koma App — storyboard e animatic')
    parser.add_argument('document', nargs='?', type=Path, help='Documento .koma para abrir')
    parser.add_argument('--diagnostics', type=Path, metavar='REPORT.json', help='Validar instalação offline e gerar relatório')
    parser.add_argument('--video', action='store_true', help='Incluir MP4 no diagnóstico offline')
    args = parser.parse_args()
    if args.diagnostics:
        from koma.diagnostics import run
        return run(args.diagnostics, video=args.video)
    from koma.ui import drop_runtime
    drop_runtime.configure()
    ft.run(lambda page: mount(page, args.document))
