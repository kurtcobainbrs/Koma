"""Upgrade leaf-boundary connections to node-owned group interfaces (format 7)."""
from dataclasses import replace
from koma.editor.models import StoryLink
from koma.editor.sequences import SequenceIndex


def migrate_sequences(board):
    index = SequenceIndex(board)
    containers = sorted((frame.id for frame in board.frames if frame.sequence),
        key=lambda key: len(index.ancestors(key)), reverse=True)
    for identifier in containers:
        index = SequenceIndex(board)
        node = index.nodes[identifier]
        members = set(node.sequence.members)
        incoming = [edge for edge in board.links if edge.target in members and edge.source not in members]
        outgoing = [edge for edge in board.links if edge.source in members and edge.target not in members]
        if len(incoming) > 1 or len(outgoing) > 1:
            raise ValueError('A sequência antiga tem ligações externas ambíguas. O arquivo foi preservado.')
        heads = [key for key in node.sequence.members if index.previous.get(key) not in members]
        tails = [key for key in node.sequence.members if index.following.get(key) not in members]
        state = replace(node.sequence,
            entry=incoming[0].target if incoming else heads[0] if heads else None,
            exit=outgoing[0].source if outgoing else tails[-1] if tails else None)
        links = tuple(StoryLink(identifier if edge.source in members and edge.target not in members else edge.source,
            identifier if edge.target in members and edge.source not in members else edge.target) for edge in board.links)
        board = replace(board, frames=tuple(replace(frame, sequence=state) if frame.id == identifier else frame
            for frame in board.frames), links=links)
    return board
