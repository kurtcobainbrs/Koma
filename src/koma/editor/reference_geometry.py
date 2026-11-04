"""Stable logical world covering the model limits without camera rebasing."""
from dataclasses import dataclass
from koma.editor.geometry import CANVAS_EDGE_MARGIN
from koma.editor.reference_models import MAX_REFERENCE_POSITION, MAX_REFERENCE_SIZE

REFERENCE_ORIGIN = MAX_REFERENCE_POSITION + CANVAS_EDGE_MARGIN
REFERENCE_WORLD_SIZE = REFERENCE_ORIGIN * 2 + MAX_REFERENCE_SIZE


@dataclass(frozen=True)
class ReferenceExtent:
    width: float = REFERENCE_WORLD_SIZE
    height: float = REFERENCE_WORLD_SIZE
    x: float = REFERENCE_ORIGIN
    y: float = REFERENCE_ORIGIN
