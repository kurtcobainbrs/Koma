"""Reorder one scene's links and canvas slots in a single history operation."""
from dataclasses import replace
from koma.editor.models import StoryLink
from koma.editor.graph import ordered
from koma.editor.scenes import scene_frames


async def reorder(player, source, target, *, after=False, expected=None):
    view = player.view
    if not view.editable() or player.editing or (expected and (expected[0] is not view.board or expected[1] is not view.session)):
        return
    board, root = view.board, player.timeline.root
    sequence = list(scene_frames(ordered(board), root) if root else ordered(board).frames)
    ids = [frame.id for frame in sequence]
    if source == target or source not in ids or target not in ids:
        return
    ids.remove(source)
    ids.insert(ids.index(target) + int(after), source)
    if ids == [frame.id for frame in sequence]:
        return
    # Follow the existing layout, including rows and manually placed positions.
    # Insertion shifts every affected card into the preceding sequence's slots.
    positions = dict(zip(ids, ((frame.x, frame.y) for frame in sequence)))
    frames = tuple(replace(frame, x=positions[frame.id][0], y=positions[frame.id][1])
        if frame.id in positions else frame for frame in board.frames)
    chain = ([root.id] if root else []) + ids
    members = set(chain)
    links = tuple(edge for edge in board.links if edge.source not in members and edge.target not in members)
    links += tuple(StoryLink(a, b) for a, b in zip(chain, chain[1:]))
    await player.media.commit(replace(board, frames=frames, links=links), label='Reordenar quadros')
    view.refresh()
    view.page.update(view.content)
    await view.workspace.compensate_origin()
    index = next((i for i, frame in enumerate(player.timeline.frames) if frame.id == source), None)
    if index is not None:
        player.strip.navigator.seek(player.timeline.starts[index])
