"""Pertencimento de cena pelas ligações, independente da posição dos nodes."""


def resolve_scene(board, identifier=None, *, fallback=None):
    """Prefer a node's scene, then a remembered scene, then the first scene."""
    return (principal(board, identifier) or principal(board, fallback)
        or next((frame for frame in board.frames if frame.node_type.starts_scene), None))


def principal(board, identifier, *, index=None):
    from koma.editor.sequences import SequenceIndex
    try:
        index = index if index is not None else SequenceIndex(board)
        ancestors = index.ancestors(identifier)
        identifier = ancestors[-1] if ancestors else identifier
    except ValueError:
        return None
    frames, previous = index.nodes, index.previous
    while identifier in frames:
        frame = frames[identifier]
        if frame.node_type.starts_scene:
            return frame
        identifier = previous.get(identifier)
    return None


def scene_frames(board, root):
    from koma.editor.sequences import SequenceIndex
    index = SequenceIndex(board)
    frames, following = index.nodes, index.following
    result = []
    identifier = following.get(root.id)
    while identifier in frames:
        frame = frames[identifier]
        if frame.node_type.starts_scene:
            break
        result.extend(index.playback(identifier))
        identifier = following.get(identifier)
    return tuple(result)
