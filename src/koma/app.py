"""Janela desktop com documentos independentes em abas de documentos."""

import argparse
import asyncio
from dataclasses import replace
from pathlib import Path

import flet as ft

from koma.documents.session import DocumentSession
from koma.editor.view import StoryboardView
from koma.editor.models import Storyboard
from koma.paths import data_directory
from koma.preferences import AppPreferences
from koma.ui.design import BACKGROUND, app_theme
from koma.ui.typography import register_fonts
from koma.ui.project_tabs import ProjectTabs


class KomaApplication:
    def __init__(self, page, directory, document=None):
        self.page = page
        self.page.title = 'Koma App'
        self.settings = AppPreferences(directory)
        self.closing_attempt = self.transitioning = False
        self.views = []
        self.untitled_number = 0
        self.view = self.make_view(DocumentSession(directory))
        self.views.append(self.view)
        self.menu_host = ft.Container(content=self.view.chrome.content)
        self.editor_host = ft.Container(content=self.view.content, expand=True)
        self.tabs = ProjectTabs(self)
        self.host = ft.Column([self.menu_host, self.tabs.content, self.editor_host], expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.document = document

    def make_view(self, session):
        if session.path is None and session.recovered_from is None and session.board == Storyboard():
            self.untitled_number += 1
            session.board = session.saved_board = replace(session.board, title=f'Projeto {self.untitled_number}')
        view = StoryboardView(self.page, session, self.settings,
            on_session=self.switch_session, on_state=self.editor_changed)
        view.content.controls.remove(view.chrome.content)
        view.can_save_to = lambda path: self.can_save_to(view, path)
        return view

    def editor_changed(self, view):
        if hasattr(self, 'tabs') and view in self.views:
            self.tabs.sync()
            if not self.closing_attempt:
                if view is self.view:
                    self.page.update(self.menu_host, self.tabs.content)
                else:
                    self.page.update(self.tabs.content)

    def can_save_to(self, view, path):
        return not any(other is not view and other.session.path is not None
            and other.session.path.resolve() == Path(path).resolve() for other in self.views)

    def set_transition(self, value):
        self.transitioning = value
        self.editor_host.disabled = self.menu_host.disabled = value
        self.tabs.sync()
        self.page.update(self.host)

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
        if self.document:
            try:
                session = await asyncio.to_thread(DocumentSession.open, self.document, self.settings.directory)
                await self.switch_session(session)
            except (OSError, ValueError) as exc:
                self.view.notify(f'Não foi possível abrir: {exc}', 'error')
        if await asyncio.to_thread(DocumentSession.recoveries, self.settings.directory):
            self.view.notify('Há sessões anteriores disponíveis em Arquivo → Recuperar sessão.', 'warning')

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
        target.active = True
        self.menu_host.content = target.chrome.content
        self.editor_host.content = target.content
        self.tabs.sync()
        self.page.update(self.host)
        try:
            await target.activate()
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
            view.lock(True)
        self.tabs.sync()
        self.page.update(self.tabs.content)
        try:
            # Nenhuma aba é descartada até todas as confirmações terminarem.
            for view in self.views:
                if not await view.files.guard_changes():
                    return False
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
                    view.lock(False)
            self.tabs.sync()
            if not self.view.closing:
                self.page.update(self.tabs.content)


def mount(page, document=None):
    page.title = 'Koma App'
    register_fonts(page)
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = app_theme()
    page.bgcolor = BACKGROUND
    page.padding = 4
    page.window.width, page.window.height = 1180, 800
    page.window.min_width, page.window.min_height = 600, 600
    page.window.prevent_close = True
    application = KomaApplication(page, data_directory(), document)
    async def on_window_event(e):
        if e.type == ft.WindowEventType.CLOSE:
            await application.close()
    page.window.on_event = on_window_event
    page.add(application.host)
    page.run_task(application.start)
    return application


def main():
    parser = argparse.ArgumentParser(description='Koma App — storyboard e animatic')
    parser.add_argument('document', nargs='?', type=Path, help='Documento .koma para abrir')
    parser.add_argument('--diagnostics', type=Path, metavar='REPORT.json', help='Validar instalação offline e gerar relatório')
    parser.add_argument('--blender', type=Path, help='Blender usado somente no diagnóstico opcional de MP4')
    args = parser.parse_args()
    if args.diagnostics:
        from koma.diagnostics import run
        return run(args.diagnostics, args.blender)
    ft.run(lambda page: mount(page, args.document))
