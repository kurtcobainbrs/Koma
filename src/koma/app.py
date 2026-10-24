"""Entrada desktop e ciclo de vida de uma única sessão por janela."""

import argparse
import asyncio
from pathlib import Path

import flet as ft

from koma.documents.session import DocumentSession
from koma.editor.view import StoryboardView
from koma.paths import data_directory
from koma.preferences import AppPreferences
from koma.ui.design import BACKGROUND, app_theme
from koma.ui.typography import register_fonts


class KomaApplication:
    def __init__(self, page, directory, document=None):
        self.page = page
        self.settings = AppPreferences(directory)
        self.closing_attempt = False
        self.view = StoryboardView(page, DocumentSession(directory), self.settings, on_session=self.switch_session)
        self.host = ft.Container(content=self.view.content, expand=True)
        self.document = document

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

    async def switch_session(self, session):
        old = self.view
        candidate = StoryboardView(self.page, session, self.settings, on_session=self.switch_session)
        self.host.content = candidate.content
        self.page.update(self.host)
        try:
            await candidate.activate()
            if candidate.load_error:
                raise ValueError(candidate.load_error)
            await old.shutdown()
        except Exception:
            self.host.content = old.content
            self.page.update(self.host)
            await candidate.shutdown()
            old.chrome.sync()
            raise
        self.view = candidate
        # O encerramento dos gestos da view anterior pode sincronizar seu título.
        candidate.chrome.sync()
        self.page.update()
        await asyncio.to_thread(old.session.close, resolved=True)

    async def close(self):
        view = self.view
        if self.closing_attempt or view.closing:
            return False
        if view.busy:
            view.notify('Aguarde a operação terminar ou cancele a exportação antes de fechar.', 'warning')
            return False
        self.closing_attempt = True
        view.lock(True)
        try:
            if not await view.files.guard_changes():
                return False
            await view.shutdown()
            await asyncio.to_thread(view.session.close, resolved=True)
            await self.page.window.destroy()
            return True
        except (OSError, ValueError, RuntimeError) as exc:
            view.closing = False
            if view.shortcuts_changed not in view.keymap.listeners:
                view.keymap.listeners.append(view.shortcuts_changed)
            view.notify(f'Não foi possível fechar com segurança: {exc}', 'error')
            return False
        finally:
            self.closing_attempt = False
            if not view.closing:
                view.lock(False)


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
