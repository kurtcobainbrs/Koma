"""Media-only native color transform; weak registrations retain no project data."""
import weakref
import flet as ft
from flet.controls.base_control import control
from koma.media_filters import selected_filter
from koma.ui import drop_runtime
from koma.ui.retained_container import RetainedContainer, retain_children


@control('koma_media_filter')
class MediaFilter(ft.LayoutControl):
    content: ft.Control | None = None
    matrix: list[float] | None = None


def media_filter(view, content, **layout):
    if not drop_runtime.supports('media_filter_v1'):
        return ft.Container(content=content, **layout)
    filtered = MediaFilter(content=RetainedContainer(content=content, hold_updates=lambda: False),
        matrix=matrix_for(view), **layout)
    registry = getattr(view, '_media_filters', None)
    if registry is None:
        registry = view._media_filters = weakref.WeakValueDictionary()
    registry[id(filtered)] = filtered
    return filtered


def matrix_for(view):
    matrix = selected_filter(view.board.media_filter).matrix
    return list(matrix) if matrix is not None else None


def refresh_media_filters(view):
    """Patch only mounted filter properties; no decoding or scene reconstruction."""
    matrix = matrix_for(view)
    updates = []
    for filtered in tuple(getattr(view, '_media_filters', {}).values()):
        filtered.matrix = matrix
        try:
            mounted = filtered.page is view.page
        except RuntimeError:
            mounted = False
        if mounted:
            updates.append(filtered)
    if updates:
        with retain_children(*(filtered.content for filtered in updates)):
            view.page.update(*updates)
