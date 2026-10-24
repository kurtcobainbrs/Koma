"""Operações puras de fluxo: uma entrada e saída por quadro, sem ciclos."""

from dataclasses import replace

from koma.editor.models import StoryGroup, StoryLink
from koma.editor.geometry import COLUMN_STEP, ROW_STEP, coordinate


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
    link = StoryLink(source, target)
    if link in board.links:
        return board
    return ordered(replace(board, links=(*board.links, link)))


def disconnect(board, links):
    return ordered(replace(board, links=tuple(link for link in board.links if link not in links)))


def remove_frames(board, identifiers, reconnect=False):
    identifiers = set(identifiers)
    outgoing = {link.source: link.target for link in board.links}
    links = [link for link in board.links if link.source not in identifiers and link.target not in identifiers]
    if reconnect:
        for link in board.links:
            if link.source not in identifiers and link.target in identifiers:
                target = link.target
                while target in identifiers:
                    target = outgoing.get(target)
                if target:
                    links.append(StoryLink(link.source, target))
    groups = tuple(replace(group, members=tuple(key for key in group.members if key not in identifiers))
                   for group in board.groups if set(group.members) - identifiers)
    return ordered(replace(board, frames=tuple(frame for frame in board.frames if frame.id not in identifiers),
                           links=tuple(links), groups=groups))


def detach(board, identifiers):
    """Solta um bloco, mantendo as conexões internas e religando o fluxo externo."""
    identifiers = set(identifiers)
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
    for identifier in selected:
        for mapping, attribute in ((outgoing, 'target'), (incoming, 'source')):
            current = identifier
            while current in mapping:
                edge = mapping[current]
                result.add(edge)
                current = getattr(edge, attribute)
    return result


def organize(board):
    board = ordered(board)
    if not board.frames:
        return board
    incoming = {edge.target for edge in board.links}
    outgoing = {edge.source: edge.target for edge in board.links}
    x = min(frame.x or 0 for frame in board.frames)
    y = min(frame.y or 0 for frame in board.frames)
    positions = {}
    for row, head in enumerate(frame for frame in board.frames if frame.id not in incoming):
        identifier, column = head.id, 0
        while identifier:
            positions[identifier] = coordinate(x + column * COLUMN_STEP), coordinate(y + row * ROW_STEP)
            identifier, column = outgoing.get(identifier), column + 1
    return replace(board, frames=tuple(replace(frame, x=positions[frame.id][0], y=positions[frame.id][1]) for frame in board.frames))


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
