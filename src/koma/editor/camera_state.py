"""Preferência de visualização por projeto, independente do documento e do histórico."""

import asyncio
import json
import math
from dataclasses import asdict, dataclass
from uuid import uuid4

from koma.editor.geometry import MIN_ZOOM, MAX_ZOOM
from koma.editor.models import MAX_POSITION


@dataclass(frozen=True)
class CameraState:
    zoom: float
    center_x: float
    center_y: float

    def valid(self):
        return all(type(v) in (int, float) and math.isfinite(v)
                   for v in (self.zoom, self.center_x, self.center_y)) and (
            MIN_ZOOM <= self.zoom <= MAX_ZOOM and
            max(abs(self.center_x), abs(self.center_y)) <= MAX_POSITION * 4)


class CameraMemory:
    def __init__(self, workspace):
        self.workspace = workspace
        self.path = workspace.view.settings.directory / 'viewports' / f'{workspace.view.store.document_id}.json'
        self.state = None
        self.revision = 0
        self.pending = False
        self.saved = None
        self.lock = asyncio.Lock()

    def read(self):
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict) or raw.get('version') != 1:
                return None
            state = CameraState(**raw['camera'])
            return state if state.valid() else None
        except (OSError, ValueError, TypeError, KeyError):
            return None

    async def load(self):
        self.state = await asyncio.to_thread(self.read)
        self.saved = self.state

    def remember(self):
        ws = self.workspace
        if not ws.initial_view_done or ws.view.load_error:
            return
        state = CameraState(ws.zoom,
            (ws.viewport_width / 2 - ws.translation_x) / ws.zoom - ws.extent.origin_x,
            (ws.viewport_height / 2 - ws.translation_y) / ws.zoom - ws.extent.origin_y)
        if state.valid():
            self.state = state
            if ws.scope.active is not None:
                ws.scope.cameras[ws.scope.active] = state
                return
            self.schedule()

    def clear(self):
        self.state = None
        self.schedule()

    def schedule(self):
        self.revision += 1
        if not self.pending and not self.workspace.view.closing:
            self.pending = True
            self.workspace.page.run_task(self.save_later)

    async def save_later(self):
        try:
            while not self.workspace.view.closing:
                revision = self.revision
                await asyncio.sleep(.3)
                if revision == self.revision:
                    await self.flush()
                    if revision == self.revision:
                        return
        finally:
            self.pending = False

    def write(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f'.{uuid4().hex}.tmp')
        try:
            temporary.write_text(json.dumps({'version': 1, 'camera': asdict(state) if state else None}), encoding='utf-8')
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    async def flush(self):
        async with self.lock:
            state = (self.workspace.scope.cameras.get(None, self.state)
                if self.workspace.scope.active is not None else self.state)
            if state == self.saved:
                return
            try:
                await asyncio.to_thread(self.write, state)
                self.saved = state
            except OSError:
                self.workspace.view.notify('Não foi possível salvar o enquadramento do storyboard.', 'warning')
