"""Compact sequence spans above frames; hierarchy comes only from node data."""
import flet as ft

from koma.ui.design import APP_PADDING, BORDER
from koma.ui.typography import TEXT_SMALL, FONT_HEADING
from koma.ui.node_path import path_text

SPAN_COLORS = (ft.Colors.PRIMARY_CONTAINER, ft.Colors.SURFACE_CONTAINER_HIGHEST)
SPAN_DIVIDER_WIDTH = 2


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
        source = (id(index), identifiers, timeline.local_editing,
            tuple(strip.player.view.settings.configuration.values['identity'].items()))
        if source != self.source:
            spans = []
            for position, identifier in enumerate(identifiers):
                root = timeline.references[position].scene if not timeline.local_editing else None
                parent = root.id if root else index.parents.get(identifier)
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
            for position, ((key, _), box) in enumerate(self.boxes.items()):
                node = index.nodes[key]
                box.bgcolor = SPAN_COLORS[position % len(SPAN_COLORS)]
                box.border = ft.Border(left=ft.BorderSide(SPAN_DIVIDER_WIDTH, ft.Colors.OUTLINE),
                    bottom=ft.BorderSide(1, BORDER))
                text = ft.Text(index.production.label(key) if node.node_type.starts_scene else node.title or node.node_type.label,
                    size=TEXT_SMALL, font_family=FONT_HEADING, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                box.content = ft.GestureDetector(content=text,
                    on_double_tap=lambda e, identifier=key: strip.player.select_scene(identifier)) if node.node_type.starts_scene else text
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
                span = timeline.durations[stop - 1] if hasattr(timeline, 'durations') else timeline.frames[stop - 1].duration
                end = timeline.starts[stop - 1] + span
                box.left = strip.scale.pixels(timeline.starts[start])
                box.width = max(0, strip.scale.pixels(end - timeline.starts[start]))
            self.geometry = geometry
        self.content.width = strip.track.width
