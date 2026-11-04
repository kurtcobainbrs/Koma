"""Execução de ações; a resolução de teclas pertence ao Keymap."""

from inspect import isawaitable
from koma.editor.shortcuts import Action


class ShortcutCommands:
    def __init__(self, navigation):
        self.nav = navigation

    async def execute(self, action):
        nav, ws, view = self.nav, self.nav.workspace, self.nav.view
        if view.work_modes.execute(action):
            return
        modes = {tool.action: tool.key for tool in nav.definitions.values()}
        if action in modes:
            nav.set_mode(modes[action])
            return
        handlers = {
            Action.COPY: lambda: view.node_clipboard.copy(view),
            Action.CUT_NODES: lambda: view.node_clipboard.copy(view, cut=True),
            Action.SEARCH: lambda: view.document_tools.search(),
            Action.IMPORT_IMAGES: view.pick_image,
            Action.NEW: view.files.new_document, Action.OPEN: view.files.open_document,
            Action.SAVE: view.files.save_document, Action.SAVE_AS: view.files.save_as,
            Action.MOVE: ws.grab.start,
            Action.PASTE: (lambda: view.node_clipboard.paste(view)) if hasattr(view, 'node_clipboard') else view.image_input.paste,
            Action.MUTE: view.toggle_muted,
            Action.INSERT: ws.context_menu.open_insert,
            Action.PROPERTIES: view.properties.toggle,
            Action.UNDO: view.graph.undo, Action.REDO: view.graph.redo,
            Action.GROUP: view.graph.group_dialog,
            Action.SEQUENCE: lambda: view.add_node('sequence'),
            Action.FOCUS: nav.focus_selected if nav.selection.ids else ws.fit,
            Action.FIT: ws.fit, Action.ALL: view.chrome.select_all,
            Action.NONE: lambda: nav.apply_selection(set()),
            Action.DUPLICATE: nav.duplicate_selected, Action.DELETE: nav.delete_selected,
            Action.CONFIRM: ws.grab.confirm, Action.CANCEL: self.cancel,
        }
        handler = handlers.get(action)
        if handler:
            result = handler()
            if isawaitable(result):
                await result

    async def cancel(self):
        nav, ws, view = self.nav, self.nav.workspace, self.nav.view
        ws.cancel_camera_transition()
        if ws.context_menu.is_open:
            ws.context_menu.dismiss()
        elif ws.secondary_pointer.press is not None:
            ws.secondary_pointer.cancel()
        elif ws.grab.active:
            ws.grab.cancel()
        elif ws.box_zoom.active:
            ws.box_zoom.cancel()
        elif view.properties.adjusting:
            view.properties.end_adjust()
            view.page.update(view.properties.content)
        elif ws.links.pending or ws.links.cut_points:
            ws.links.cancel()
            ws.links.cancel_cut()
        elif ws.drag:
            ws.cancel_drag(ws.drag.identifier)
        elif ws.box_selection.active:
            ws.box_selection.cancel()
        elif ws.scope.active is not None:
            await ws.scope.back()
        else:
            nav.set_mode('select')
            nav.select_node(None)
