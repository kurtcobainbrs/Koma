"""Reorder flow and node-owned group membership in one atomic history action."""
from dataclasses import replace
from koma.editor.models import StoryLink
from koma.editor.sequences import SequenceIndex
from koma.editor.geometry import next_position


def reordered(board, frames, source, target, *, after=False):
    index = SequenceIndex(board)
    ids = [frame.id for frame in frames]
    if source == target or source not in ids or target not in ids:
        return board
    old_parent, new_parent = index.parents.get(source), index.parents.get(target)
    previous, following = index.previous.get(source), index.following.get(source)
    links = [edge for edge in board.links if source not in (edge.source, edge.target)]
    if previous and following:
        links.append(StoryLink(previous, following))
    states = {}
    if old_parent:
        state = index.nodes[old_parent].sequence
        states[old_parent] = replace(state,
            members=tuple(key for key in state.members if key != source) if old_parent != new_parent else state.members,
            entry=following if state.entry == source else state.entry,
            exit=previous if state.exit == source else state.exit)
    if after:
        boundary = next((edge for edge in links if edge.source == target), None)
        if boundary:
            links.remove(boundary)
            links.append(StoryLink(source, boundary.target))
        links.append(StoryLink(target, source))
    else:
        boundary = next((edge for edge in links if edge.target == target), None)
        if boundary:
            links.remove(boundary)
            links.append(StoryLink(boundary.source, source))
        links.append(StoryLink(source, target))
    if new_parent:
        state = states.get(new_parent, index.nodes[new_parent].sequence)
        states[new_parent] = replace(state,
            members=state.members if source in state.members else (*state.members, source),
            entry=source if not after and state.entry == target else state.entry,
            exit=source if after and state.exit == target else state.exit)
    positions = {}
    if old_parent == new_parent:
        local = [frame for frame in frames if index.parents.get(frame.id) == old_parent]
        ids.remove(source)
        ids.insert(ids.index(target) + int(after), source)
        local_ids = [key for key in ids if index.parents.get(key) == old_parent]
        positions = dict(zip(local_ids, ((frame.x, frame.y) for frame in local)))
    else:
        positions[source] = next_position(tuple(frame for frame in board.frames
            if index.parents.get(frame.id) == new_parent and frame.id != source))
    updated = tuple(replace(frame,
        sequence=states.get(frame.id, frame.sequence),
        x=positions.get(frame.id, (frame.x, frame.y))[0],
        y=positions.get(frame.id, (frame.x, frame.y))[1])
        if frame.id in states or frame.id in positions else frame for frame in board.frames)
    if updated == board.frames and set(links) == set(board.links):
        return board
    result = replace(board, frames=updated, links=tuple(links))
    result.validate()
    return result


async def reorder(player, source, target, *, after=False, expected=None):
    view = player.view
    if not player.timeline.local_editing:
        view.notify('Reordene as cenas na lista lateral. Abra a cena para reordenar quadros.', 'info')
        return
    if not view.editable() or player.editing or (expected and (expected[0] is not view.board or expected[1] is not view.session)):
        return
    board = view.board
    try:
        updated = reordered(board, player.timeline.frames, source, target, after=after)
    except ValueError as exc:
        view.notify(str(exc), 'warning')
        return
    if updated is board:
        return
    await player.media.commit(updated, label='Reordenar quadros')
    view.refresh()
    view.page.update(view.content)
    await view.workspace.compensate_origin()
    position = next((i for i, frame in enumerate(player.timeline.frames) if frame.id == source), None)
    if position is not None:
        player.strip.navigator.seek(player.timeline.starts[position])
