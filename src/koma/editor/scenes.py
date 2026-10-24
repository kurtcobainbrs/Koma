"""Pertencimento de cena pelas ligações, independente da posição dos nodes."""


def principal(board, identifier):
    frames = {frame.id: frame for frame in board.frames}
    previous = {link.target: link.source for link in board.links}
    while identifier in frames:
        frame = frames[identifier]
        if frame.node_type.starts_scene:
            return frame
        identifier = previous.get(identifier)
    return None


def scene_frames(board, root):
    frames = {frame.id: frame for frame in board.frames}
    following = {link.source: link.target for link in board.links}
    result = []
    identifier = following.get(root.id)
    while identifier in frames:
        frame = frames[identifier]
        if frame.node_type.starts_scene:
            break
        result.append(frame)
        identifier = following.get(identifier)
    return tuple(result)
