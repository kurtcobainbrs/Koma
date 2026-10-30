"""Operações puras de fluxo: uma entrada e saída por quadro, sem ciclos."""

from dataclasses import replace

from koma.editor.models import StoryGroup, StoryLink
from koma.editor.geometry import COLUMN_STEP, ROW_STEP, coordinate
from koma.editor.group_ports import GroupPort


def ordered(board):
    board.validate()
    outgoing = {link.source: link.target for link in board.links}
    incoming = {link.target for link in board.links}
    frames = {frame.id: frame for frame in board.frames}
    result = []
    for frame in board.frames:
        if frame.id not in incoming:
            identifier = frame.id
            while identifier:
                result.append(frames[identifier])
                identifier = outgoing.get(identifier)
    return replace(board, frames=tuple(result))


def connect(board, source, target):
    from koma.editor.sequences import SequenceIndex
    index = SequenceIndex(board)
    port = source if isinstance(source, GroupPort) else target if isinstance(target, GroupPort) else None
    if port is not None:
        child = target if source is port else source
        if isinstance(child, GroupPort) or port.group not in index.nodes or index.parents.get(child) != port.group:
            raise ValueError('Conecte a interface a um membro da sequência.')
        if (source is port and port.output) or (target is port and not port.output):
            raise ValueError('Conecte Entrada → quadros → Saída.')
        node = index.nodes[port.group]
        if not node.sequence:
            raise ValueError('Interface de sequência inválida.')
        state = replace(node.sequence, **{'exit' if port.output else 'entry': child})
        links = tuple(edge for edge in board.links
            if not (edge.source == child if port.output else edge.target == child))
        return ordered(replace(board, frames=tuple(replace(frame, sequence=state) if frame.id == node.id
            else frame for frame in board.frames), links=links))
    source, target = index.endpoint(source, True), index.endpoint(target, False)
    link = StoryLink(source, target)
    if link in board.links:
        return board
    parent = index.parents.get(source)
    if parent and parent == index.parents.get(target):
        node = index.nodes[parent]
        state = replace(node.sequence, entry=None if node.sequence.entry == target else node.sequence.entry,
            exit=None if node.sequence.exit == source else node.sequence.exit)
        board = replace(board, frames=tuple(replace(frame, sequence=state) if frame.id == parent else frame for frame in board.frames))
    return ordered(replace(board, links=(*board.links, link)))


def disconnect(board, links):
    result = board
    for edge in links:
        port = edge.source if isinstance(edge.source, GroupPort) else edge.target if isinstance(edge.target, GroupPort) else None
        if port is not None:
            node = next(frame for frame in result.frames if frame.id == port.group)
            result = result.change(node.id, sequence=replace(node.sequence, **{'exit' if port.output else 'entry': None}))
    return ordered(replace(result, links=tuple(link for link in result.links if link not in links)))


def remove_frames(board, identifiers, reconnect=False):
    from koma.editor.sequences import SequenceIndex
    index = SequenceIndex(board)
    identifiers = index.closure(identifiers)
    repair = identifiers if reconnect else {key for key in identifiers
        if any(parent not in identifiers for parent in index.ancestors(key))}
    def surviving_port(key, mapping):
        while key in identifiers:
            key = mapping.get(key)
        return key
    outgoing = {link.source: link.target for link in board.links}
    links = [link for link in board.links if link.source not in identifiers and link.target not in identifiers]
    if repair:
        for link in board.links:
            if link.source not in identifiers and link.target in repair:
                target = link.target
                while target in identifiers:
                    target = outgoing.get(target)
                if target:
                    links.append(StoryLink(link.source, target))
    groups = tuple(replace(group, members=tuple(key for key in group.members if key not in identifiers))
                   for group in board.groups if set(group.members) - identifiers)
    frames = tuple(replace(frame, sequence=replace(frame.sequence,
        members=tuple(key for key in frame.sequence.members if key not in identifiers),
        entry=surviving_port(frame.sequence.entry, index.following),
        exit=surviving_port(frame.sequence.exit, index.previous)))
        if frame.sequence else frame for frame in board.frames if frame.id not in identifiers)
    return ordered(replace(board, frames=frames,
                           links=tuple(links), groups=groups,
                           audio_tracks=tuple(track for track in board.audio_tracks if track.scene_id not in identifiers),
                           markers=tuple(marker for marker in board.markers if marker.scene_id not in identifiers)))


def detach(board, identifiers):
    """Solta um bloco, mantendo as conexões internas e religando o fluxo externo."""
    identifiers = set(identifiers)
    from koma.editor.sequences import SequenceIndex
    if not SequenceIndex(board).can_detach(identifiers):
        raise ValueError('Dissolva a sequência para soltar seus quadros do fluxo.')
    remaining = remove_frames(board, identifiers, reconnect=True)
    internal = tuple(link for link in board.links if link.source in identifiers and link.target in identifiers)
    return ordered(replace(board, links=(*remaining.links, *internal)))


def insert(board, identifier, link):
    if link not in board.links or identifier in (link.source, link.target):
        raise ValueError('Escolha uma ligação entre outros quadros.')
    source = next((frame for frame in board.frames if frame.id == identifier), None)
    if source is None:
        raise ValueError('Quadro indisponível.')
    previous = next((edge.source for edge in board.links if edge.target == identifier), None)
    following = next((edge.target for edge in board.links if edge.source == identifier), None)
    links = [edge for edge in board.links if identifier not in (edge.source, edge.target) and edge != link]
    if previous and following:
        links.append(StoryLink(previous, following))
    links.extend((StoryLink(link.source, identifier), StoryLink(identifier, link.target)))
    return ordered(replace(board, links=tuple(links)))


def path_links(board, selected):
    outgoing = {edge.source: edge for edge in board.links}
    incoming = {edge.target: edge for edge in board.links}
    result = set()
    visited = {attribute: set() for attribute in ('target', 'source')}
    for identifier in selected:
        for mapping, attribute in ((outgoing, 'target'), (incoming, 'source')):
            current = identifier
            while current in mapping and current not in visited[attribute]:
                visited[attribute].add(current)
                edge = mapping[current]
                result.add(edge)
                current = getattr(edge, attribute)
    return result


def organize(board):
    board = ordered(board)
    positions = layout_positions(board.frames, board.links)
    return replace(board, frames=tuple(replace(frame, x=positions[frame.id][0], y=positions[frame.id][1]) for frame in board.frames))


def layout_positions(frames, links):
    """Layout a visible flow without modifying or validating a partial document."""
    if not frames:
        return {}
    incoming = {edge.target for edge in links}
    outgoing = {edge.source: edge.target for edge in links}
    x = min(frame.x or 0 for frame in frames)
    y = min(frame.y or 0 for frame in frames)
    positions = {}
    for row, head in enumerate(frame for frame in frames if frame.id not in incoming):
        identifier, column = head.id, 0
        while identifier:
            positions[identifier] = coordinate(x + column * COLUMN_STEP), coordinate(y + row * ROW_STEP)
            identifier, column = outgoing.get(identifier), column + 1
    return positions


def group_frames(board, identifiers, title, group_id=None):
    identifiers = set(identifiers)
    if not identifiers or not identifiers <= {frame.id for frame in board.frames}:
        raise ValueError('Selecione os quadros da cena.')
    groups = [replace(group, members=tuple(key for key in group.members if key not in identifiers))
              for group in board.groups if group.id != group_id and set(group.members) - identifiers]
    members = tuple(frame.id for frame in board.frames if frame.id in identifiers)
    groups.append(StoryGroup(title=title.strip(), members=members) if group_id is None else StoryGroup(group_id, title.strip(), members))
    result = replace(board, groups=tuple(groups))
    result.validate()
    return result
