"""Transient canvas navigation; nodes and their positions remain in the document."""
import flet as ft

from koma.editor.scenes import principal
from koma.editor.sequences import append_to_sequence
from koma.editor.geometry import next_position
from koma.editor.group_ports import GroupPort, PortLink
from koma.ui.design import COMPACT_CONTROL_HEIGHT, MUTED
from koma.ui.event_updates import explicit_updates
from koma.ui.retained_container import retain_children


class SequenceScope:
    def __init__(self, workspace):
        self.workspace, self.view = workspace, workspace.view
        self.path = ()
        self.source = self.key = None
        self.visible = frozenset()
        self.representatives = {}
        self.cameras = {}
        self.selections = {}
        self.changing = False
        self.content = ft.Row(spacing=0, visible=False, scroll=ft.ScrollMode.AUTO)

    @property
    def active(self):
        return self.path[-1] if self.path else None

    def sync(self):
        index = self.view.sequences.index
        path = []
        parent = None
        for key in self.path:
            node = index.nodes.get(key)
            if not node or not node.sequence or index.parents.get(key) != parent:
                break
            path.append(key)
            parent = key
        self.path = tuple(path)
        if self.source is not self.view.board or self.key != self.path:
            self.source, self.key = self.view.board, self.path
            self.visible = frozenset(key for key in index.nodes if index.parents.get(key) == self.active)
            self.representatives = {}
            for key in index.nodes:
                current = key
                while current not in self.visible and current in index.parents:
                    current = index.parents[current]
                self.representatives[key] = current if current in self.visible else None
            valid = {None, *(key for key, node in index.nodes.items() if node.sequence)}
            self.cameras = {key: value for key, value in self.cameras.items() if key in valid}
            self.selections = {key: value for key, value in self.selections.items() if key in valid}
            self.sync_path(index)

    def representative(self, identifier):
        return self.representatives.get(identifier)

    def edges(self, board=None):
        """Project only connections whose endpoints belong to the current level."""
        for edge in (board or self.view.board).links:
            source, target = self.representative(edge.source), self.representative(edge.target)
            if source is not None and target is not None and source != target:
                yield edge, source, target
        if self.active:
            state = self.view.sequences.index.nodes[self.active].sequence
            for edge in (PortLink(GroupPort(self.active), state.entry) if state.entry else None,
                         PortLink(state.exit, GroupPort(self.active, True)) if state.exit else None):
                if edge:
                    yield edge, edge.source, edge.target

    def attach_new(self, board, identifiers):
        return append_to_sequence(board, self.active, identifiers)

    def next_position(self):
        index = self.view.sequences.index
        return next_position(tuple(index.nodes[key] for key in self.visible))

    def sync_path(self, index):
        def button(label, target):
            async def navigate(e):
                await self.show(target)
            return ft.TextButton(label, height=COMPACT_CONTROL_HEIGHT, on_click=navigate)
        controls = [button('Canvas', None)]
        if self.path:
            root = principal(self.view.board, self.path[0])
            if root:
                controls.extend((ft.Icon(ft.Icons.CHEVRON_RIGHT, size=14, color=MUTED),
                    ft.Text(self.view.production.label(root.id))))
        for key in self.path:
            controls.extend((ft.Icon(ft.Icons.CHEVRON_RIGHT, size=14, color=MUTED),
                button(index.nodes[key].title or 'Sequência', key)))
        self.content.controls = controls
        self.content.visible = bool(self.path)

    @explicit_updates
    async def show(self, identifier=None):
        if self.changing or not self.view.editable() or self.view.player.opened:
            return
        index = self.view.sequences.index
        node = index.nodes.get(identifier)
        if identifier is not None and (not node or not node.sequence):
            return
        path = tuple(reversed(index.ancestors(identifier))) + (identifier,) if identifier else ()
        if path == self.path:
            return
        self.changing = True
        ws, nav = self.workspace, self.workspace.navigation
        try:
            ws.cancel_gestures()
            self.view.properties.end_adjust()
            self.view.properties.release_field_focus()
            self.view.focus.cancel()
            ws.camera_memory.remember()
            self.cameras[self.active] = ws.camera_memory.state
            self.selections[self.active] = (set(nav.selection.ids), nav.selected)
            nav.apply_selection(set())
            self.path = path
            self.sync()
            for key, card in self.view.cards.items():
                card.content.visible = key in self.visible
            nav.reset_keys()
            nav.sync(update=False)
            ws.context_menu.pointer = None
            ws.refresh()
            ids, active = self.selections.get(identifier, (set(), None))
            nav.apply_selection(ids, active)
            self.view.properties.sync()
            with retain_children(*(card.box.content for card in self.view.cards.values()), ws.background):
                self.view.page.update(ws.content, self.content, self.view.properties.content)
            ws.camera_memory.state = self.cameras.get(identifier)
            await ws.restore_camera()
            nav.focus_keyboard()
        finally:
            self.changing = False

    async def back(self):
        await self.show(self.path[-2] if len(self.path) > 1 else None)

    async def reveal(self, identifiers):
        index = self.view.sequences.index
        keys = [key for key in identifiers if key in index.nodes]
        if not keys:
            return
        parent = index.parents.get(keys[0])
        if any(index.parents.get(key) != parent for key in keys):
            # A multi-scope result is represented by its containers on the root canvas.
            parent = None
        await self.show(parent)
