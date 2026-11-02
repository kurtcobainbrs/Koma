"""Transactional node copies with owned assets and fresh document identifiers."""

import asyncio
import shutil
import tempfile
from dataclasses import dataclass, replace
from uuid import uuid4
import flet as ft

from koma.editor.models import MAX_CARDS, Storyboard, StoryLink, StoryGroup
from koma.editor.geometry import group_delta
from koma.documents.images import load_thumbnails
from koma.editor.sequences import SequenceIndex, remap_frame
from koma.editor.node_media import frame_assets
from pathlib import Path
from flet.controls.exceptions import FletException

MAX_CLIPBOARD_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class NodeSelection:
    frames: tuple
    links: tuple
    groups: tuple
    tracks: tuple
    markers: tuple
    assets: dict
    lease: object = None

    def __del__(self):
        if self.lease is not None:
            self.lease.cleanup()


async def capture_selection(board, store, identifiers):
    """Own the source assets without depending on a view or system clipboard."""
    ids = frozenset(SequenceIndex(board).closure(identifiers))
    frames = tuple(frame for frame in board.frames if frame.id in ids)
    if not frames:
        return None
    whole = len(frames) == len(board.frames)
    tracks = tuple(track for track in board.audio_tracks if track.scene_id in ids or (whole and not track.scene_id))
    markers = tuple(marker for marker in board.markers if marker.scene_id in ids or (whole and not marker.scene_id))
    assets = set().union(*(frame_assets(frame) for frame in frames))
    assets.update(('audio', track.asset) for track in tracks)
    def read():
        paths = {(kind, name): getattr(store, kind) / name for kind, name in assets}
        if sum(path.stat().st_size for path in paths.values()) > MAX_CLIPBOARD_BYTES:
            raise ValueError('A seleção excede o limite de 512 MB da área de transferência.')
        lease = tempfile.TemporaryDirectory(prefix='koma-clipboard-')
        captured = {}
        try:
            for key, path in paths.items():
                if key[0] == 'videos':
                    target = Path(lease.name) / path.name
                    shutil.copyfile(path, target)
                    captured[key] = target
                else:
                    captured[key] = path.read_bytes()
            return captured, lease
        except Exception:
            lease.cleanup()
            raise
    captured, lease = await asyncio.to_thread(read)
    return NodeSelection(frames, tuple(edge for edge in board.links if edge.source in ids and edge.target in ids),
        tuple(group for group in board.groups if set(group.members) <= ids), tracks, markers,
        captured, lease)


class NodeClipboard:
    def __init__(self):
        self.payload = None
        self.token = ''

    async def copy(self, view, *, cut=False):
        if not view.editable():
            return
        board, session = view.board, view.session
        ids = frozenset(view.workspace.navigation.selection.ids)
        try:
            payload = await capture_selection(board, view.store, ids)
            if payload is None:
                return
            if view.board is not board or view.session is not session or not view.editable():
                return
            token = 'koma-nodes:' + uuid4().hex
            await ft.Clipboard().set(token)
            if view.board is not board or view.session is not session or not view.editable():
                return
            self.token = token
            self.payload = payload
            if cut and view.board is board and view.session is session:
                from koma.editor.graph import remove_frames
                await view.graph.commit(remove_frames(board, ids), label='Recortar nodes')
            view.notify(f'{len(payload.frames)} nodes {"recortados" if cut else "copiados"}.', 'success')
            return True
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            view.notify(str(exc), 'warning')

    async def paste(self, view, *, operation='Colar nodes'):
        if not view.editable():
            return
        try:
            token = await ft.Clipboard().get()
        except (OSError, RuntimeError, FletException) as exc:
            view.notify(f'Não foi possível ler a área de transferência: {exc}', 'warning')
            return
        if not view.editable():
            return
        if not self.payload or token != self.token:
            await view.image_input.paste()
            return
        await self.insert(view, self.payload, operation=operation)

    async def insert(self, view, payload, *, operation='Colar nodes'):
        if payload is None or not view.editable():
            return
        board, session = view.board, view.session
        store = view.store
        frames, edges, groups = payload.frames, payload.links, payload.groups
        tracks, markers, assets = payload.tracks, payload.markers, payload.assets
        if len(board.frames) + len(frames) > MAX_CARDS:
            view.notify('A seleção ultrapassa o limite de quadros do projeto.', 'warning')
            return
        mapping = {frame.id: uuid4().hex for frame in frames}
        names = {key: uuid4().hex + Path(key[1]).suffix for key in assets}
        ws = view.workspace
        from koma.editor.canvas_position import insertion_position
        anchor = insertion_position(ws)
        roots = set(SequenceIndex(Storyboard(frames=frames, links=edges)).roots(mapping))
        positions = {frame.id: (frame.x or 0, frame.y or 0) for frame in frames}
        root_positions = {key: positions[key] for key in roots}
        left, top = min(x for x, _ in root_positions.values()), min(y for _, y in root_positions.values())
        dx, dy = group_delta(root_positions, anchor[0] - left,
            anchor[1] - top, anchor=(left, top), snap=ws.snap_enabled,
            step=view.settings.configuration.values['canvas']['spacing'])
        copies = tuple(remap_frame(frame, mapping, x=positions[frame.id][0] + (dx if frame.id in roots else 0),
            y=positions[frame.id][1] + (dy if frame.id in roots else 0),
            media=tuple(entry.remap_assets(names) for entry in frame.media)) for frame in frames)
        result = replace(board, frames=(*board.frames, *copies),
            links=(*board.links, *(StoryLink(mapping[e.source], mapping[e.target]) for e in edges)),
            groups=(*board.groups, *(StoryGroup(title=g.title, members=tuple(mapping[i] for i in g.members)) for g in groups)),
            audio_tracks=(*board.audio_tracks, *(replace(t, id=uuid4().hex, asset=names['audio', t.asset], scene_id=mapping.get(t.scene_id, '')) for t in tracks)),
            markers=(*board.markers, *(replace(m, id=uuid4().hex, scene_id=mapping.get(m.scene_id, '')) for m in markers)))
        written = []
        view.lock(True)
        try:
            result = ws.scope.attach_new(result, (frame.id for frame in copies))
            result.validate()
            def write():
                for key, data in assets.items():
                    target = getattr(store, key[0]) / names[key]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    written.append(target)
                    if isinstance(data, Path):
                        shutil.copyfile(data, target)
                    else:
                        target.write_bytes(data)
                return load_thumbnails(Storyboard(frames=copies), store)
            thumbnails = await asyncio.to_thread(write)
            if view.board is not board or view.session is not session or not view.active or view.closing:
                raise ValueError('O documento mudou durante a colagem.')
            view.lock(False)
            view.thumbnails.update(thumbnails)
            await view.graph.commit(result, label=operation)
            written.clear()
            ws.navigation.apply_selection(set(mapping.values()), copies[-1].id)
        except (OSError, ValueError, RuntimeError, FletException) as exc:
            view.notify(f'Não foi possível colar: {exc}', 'warning')
        finally:
            if view.board is board:
                for path in written:
                    path.unlink(missing_ok=True)
            view.lock(False)
