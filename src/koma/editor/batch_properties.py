"""One validated transaction for compatible selected nodes."""
from dataclasses import replace


def property_targets(board, identifiers, key):
    frames = [frame for frame in board.frames if frame.id in identifiers]
    if key in ('duration', 'subtitle', 'audio', 'drawing'):
        return [frame for frame in frames if frame.node_type.timed]
    if key in ('image', 'image_fit', 'crop_x', 'crop_y'):
        return [frame for frame in frames if frame.node_type.image]
    if key == 'scene_color':
        return [frame for frame in frames if frame.node_type.starts_scene]
    return frames


async def apply_properties(view, identifiers, values, coalesce_key=None):
    if not view.editable() or not values:
        return
    targets = set(identifiers)
    for key in values:
        targets.intersection_update(frame.id for frame in property_targets(view.board, identifiers, key))
    if not targets:
        return
    board = replace(view.board, frames=tuple(replace(frame, **values) if frame.id in targets else frame
        for frame in view.board.frames))
    try:
        board.validate()
    except ValueError as exc:
        view.notify(str(exc), 'warning')
        return
    view.changed(board, coalesce_key)
    view.refresh()
    view.page.update(view.content)
    await view.persist()
