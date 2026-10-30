"""Compact sequence spans above frames; hierarchy comes only from node data."""
import flet as ft

from koma.ui.design import APP_PADDING, BORDER
from koma.ui.typography import TEXT_SMALL
from koma.ui.node_path import path_text


class SequenceLane:
    def __init__(self, strip):
        self.strip = strip
        self.source = self.geometry = None
        self.spans = ()
        self.boxes = {}
        self.height = 0
        self.content = ft.Stack(left=0, top=strip.style.frames_top, height=0, visible=False,
            clip_behavior=ft.ClipBehavior.HARD_EDGE)

    def sync(self, identifiers):
        strip = self.strip
        timeline = strip.player.timeline
        index = strip.player.view.sequences.index
        source = (id(index), identifiers)
        if source != self.source:
            spans = []
            for position, identifier in enumerate(identifiers):
                parent = index.parents.get(identifier)
                if parent is None:
                    continue
                if spans and spans[-1][0] == parent and spans[-1][2] == position:
                    spans[-1] = (parent, spans[-1][1], position + 1)
                else:
                    spans.append((parent, position, position + 1))
            self.spans = tuple(spans)
            self.boxes = {(key, start): self.boxes.get((key, start)) or ft.Container(
                top=0, height=strip.style.sequence_height, padding=ft.Padding.symmetric(horizontal=APP_PADDING),
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
                content=ft.Text(size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
                for key, start, _ in spans}
            for (key, _), box in self.boxes.items():
                node = index.nodes[key]
                box.content.value = node.title or node.node_type.label
                box.tooltip = path_text(index, key)
            self.content.controls = list(self.boxes.values())
            self.height = strip.style.sequence_height if spans else 0
            self.content.height = self.height
            self.content.visible = bool(spans)
            self.source = source
            self.geometry = None
        geometry = (id(timeline), strip.scale)
        if strip.scale and geometry != self.geometry:
            for key, start, stop in self.spans:
                box = self.boxes[key, start]
                end = timeline.starts[stop - 1] + timeline.frames[stop - 1].duration
                box.left = strip.scale.pixels(timeline.starts[start])
                box.width = max(0, strip.scale.pixels(end - timeline.starts[start]))
            self.geometry = geometry
        self.content.width = strip.track.width
