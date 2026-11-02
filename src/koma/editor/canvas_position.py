"""Shared viewport-to-document anchor for imports and pasting."""
def insertion_position(workspace):
    point = workspace.context_menu.pointer or (
        (workspace.viewport_width / 2 - workspace.translation_x) / workspace.zoom,
        (workspace.viewport_height / 2 - workspace.translation_y) / workspace.zoom)
    return point[0] - workspace.extent.origin_x, point[1] - workspace.extent.origin_y
