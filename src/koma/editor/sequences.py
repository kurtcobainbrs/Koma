"""Derived hierarchy, visibility and flow endpoints; no UI or copied node data."""
from dataclasses import replace
from koma.editor.models import StoryFrame, StoryLink, MAX_CARDS
from koma.editor.sequence_models import SequenceState


class SequenceIndex:
    def __init__(self, board):
        self.board = board
        self.nodes = {frame.id: frame for frame in board.frames}
        self.following = {edge.source: edge.target for edge in board.links}
        self.previous = {edge.target: edge.source for edge in board.links}
        self.parents = {}
        self._connected_paths = {}
        for frame in board.frames:
            if frame.node_type.contains_frames:
                for key in frame.sequence.members:
                    if key not in self.nodes or key == frame.id or key in self.parents:
                        raise ValueError('Cada quadro deve pertencer a uma única sequência válida.')
                    if not (self.nodes[key].node_type.timed or self.nodes[key].node_type.contains_frames):
                        raise ValueError('Inícios de cena não podem fazer parte de uma sequência.')
                    self.parents[key] = frame.id
        for identifier in self.parents:
            visited = {identifier}
            parent = self.parents[identifier]
            while parent:
                if parent in visited:
                    raise ValueError('Uma sequência não pode conter a si mesma.')
                visited.add(parent)
                parent = self.parents.get(parent)

    def closure(self, identifiers):
        result, pending = set(), list(identifiers)
        while pending:
            key = pending.pop()
            if key in result or key not in self.nodes:
                continue
            result.add(key)
            frame = self.nodes[key]
            if frame.node_type.contains_frames:
                pending.extend(frame.sequence.members)
        return result

    def roots(self, identifiers):
        identifiers = set(identifiers)
        return tuple(frame.id for frame in self.board.frames if frame.id in identifiers
            and not any(parent in identifiers for parent in self.ancestors(frame.id)))

    def ancestors(self, identifier):
        result = []
        while identifier in self.parents:
            identifier = self.parents[identifier]
            result.append(identifier)
        return result

    def path(self, identifier):
        """Return the original nodes along scene, containers and target."""
        from koma.editor.scenes import principal
        if identifier not in self.nodes:
            return ()
        keys = [*reversed(self.ancestors(identifier)), identifier]
        root = principal(self.board, identifier, index=self)
        if root and root.id not in keys:
            keys.insert(0, root.id)
        return tuple(self.nodes[key] for key in keys)

    def representative(self, identifier):
        result = identifier
        for parent in self.ancestors(identifier):
            if self.nodes[parent].sequence.collapsed:
                result = parent
        return result

    def leaves(self, identifiers):
        selected = {key for key in self.closure(identifiers) if self.nodes[key].node_type.timed}
        result, visited = [], set()
        for frame in self.board.frames:
            key = frame.id
            if key not in selected or self.previous.get(key) in selected:
                continue
            while key in selected and key not in visited:
                visited.add(key)
                result.append(self.nodes[key])
                key = self.following.get(key)
        return tuple(result)

    def total(self, identifier):
        return sum(frame.duration for frame in self.playback(identifier) if not frame.muted)

    def connected_path(self, identifier):
        pending = [(identifier, None)]
        while pending:
            group, path = pending.pop()
            if group in self._connected_paths:
                continue
            if path is not None:
                self._connected_paths[group] = path if all(self._connected_paths[key]
                    for key in path if self.nodes[key].sequence) else ()
                continue
            state = self.nodes[group].sequence
            path, visited = [], set()
            key = state.entry if state else None
            members = set(state.members) if state else set()
            while key in members and key not in visited:
                visited.add(key)
                path.append(key)
                if key == state.exit:
                    break
                key = self.following.get(key)
            if not path or key != state.exit:
                self._connected_paths[group] = ()
                continue
            pending.append((group, tuple(path)))
            pending.extend((key, None) for key in path if self.nodes[key].sequence and key not in self._connected_paths)
        return self._connected_paths[identifier]

    def playback(self, identifier):
        result, pending = [], [identifier]
        while pending:
            frame = self.nodes[pending.pop()]
            if frame.node_type.timed:
                result.append(frame)
            elif frame.sequence:
                pending.extend(reversed(self.connected_path(frame.id)))
        return tuple(result)

    def endpoint(self, identifier, output):
        return identifier

    def can_detach(self, identifiers):
        identifiers = set(identifiers)
        return identifiers <= self.nodes.keys()

    def validate_flow(self):
        for frame in self.nodes.values():
            if frame.sequence:
                if frame.sequence.entry in self.previous or frame.sequence.exit in self.following:
                    raise ValueError('Cada conector aceita uma ligação. Ajuste a Entrada ou a Saída do grupo.')
        for edge in self.board.links:
            if self.parents.get(edge.source) != self.parents.get(edge.target):
                raise ValueError('Conecte nodes do mesmo nível. Use a Entrada e a Saída da sequência.')


def remap_frame(frame, identifiers, **values):
    return replace(frame, id=identifiers[frame.id],
        sequence=frame.sequence.remap(identifiers) if frame.sequence is not None else None, **values)


def compose(board, identifiers, *, spec, title, position):
    if not spec.contains_frames:
        raise ValueError('O tipo de node não aceita uma composição de quadros.')
    index = SequenceIndex(board)
    roots = index.roots(key for key in identifiers if key in index.nodes
        and (index.nodes[key].node_type.timed or index.nodes[key].sequence))
    parents = {index.parents.get(key) for key in roots}
    if len(parents) > 1:
        raise ValueError('Selecione quadros do mesmo nível para criar a sequência.')
    parent = next(iter(parents), None)
    selected = set(roots)
    incoming = [edge for edge in board.links if edge.target in selected and edge.source not in selected]
    outgoing = [edge for edge in board.links if edge.source in selected and edge.target not in selected]
    if len(incoming) > 1 or len(outgoing) > 1:
        raise ValueError('O grupo aceita uma Entrada e uma Saída. Ajuste as ligações externas antes de agrupar.')
    heads = [key for key in roots if index.previous.get(key) not in selected]
    tails = [key for key in roots if index.following.get(key) not in selected]
    entry = incoming[0].target if incoming else heads[0] if heads else None
    exit = outgoing[0].source if outgoing else tails[-1] if tails else None
    if roots:
        position = min(index.nodes[key].x for key in roots), min(index.nodes[key].y for key in roots)
    node = StoryFrame(kind=spec.kind, title=title, x=position[0], y=position[1],
        sequence=SequenceState(roots, entry=entry, exit=exit))
    if len(board.frames) >= MAX_CARDS:
        raise ValueError(f'O storyboard aceita até {MAX_CARDS} nodes.')
    frames = []
    for frame in board.frames:
        if frame.id == parent:
            state = frame.sequence
            frame = replace(frame, sequence=replace(state,
                members=tuple(key for key in state.members if key not in selected) + (node.id,),
                entry=node.id if state.entry in selected else state.entry,
                exit=node.id if state.exit in selected else state.exit))
        frames.append(frame)
    links = tuple(StoryLink(node.id if edge.source in selected and edge.target not in selected else edge.source,
        node.id if edge.target in selected and edge.source not in selected else edge.target) for edge in board.links)
    result = replace(board, frames=(*frames, node), links=links)
    result.validate()
    return result, node.id


def append_to_sequence(board, identifier, identifiers):
    if identifier is None:
        return board
    index = SequenceIndex(board)
    parent = index.nodes[identifier]
    roots = index.roots(identifiers)
    if any(index.parents.get(key) is not None or index.nodes[key].node_type.starts_scene for key in roots):
        raise ValueError('Uma sequência aceita quadros e outras sequências. Crie cenas no canvas principal.')
    if not roots:
        return board
    links = list(board.links)
    chain = ((parent.sequence.exit,) if parent.sequence.exit else ()) + roots
    for a, b in zip(chain, chain[1:]):
        edge = StoryLink(a, b)
        if edge not in links:
            links.append(edge)
    updated = replace(parent, sequence=replace(parent.sequence,
        members=(*parent.sequence.members, *roots), entry=parent.sequence.entry or roots[0], exit=roots[-1]))
    return replace(board, frames=tuple(updated if frame.id == identifier else frame for frame in board.frames), links=tuple(links))


def dissolve(board, identifier):
    index = SequenceIndex(board)
    node = index.nodes[identifier]
    state = node.sequence
    previous, following = index.previous.get(identifier), index.following.get(identifier)
    frames = []
    for frame in board.frames:
        if frame.id == identifier:
            continue
        if frame.sequence and identifier in frame.sequence.members:
            container = frame.sequence
            frame = replace(frame, sequence=replace(container,
                members=tuple(child for key in container.members for child in (state.members if key == identifier else (key,))),
                entry=state.entry if container.entry == identifier else container.entry,
                exit=state.exit if container.exit == identifier else container.exit))
        frames.append(frame)
    links = [edge for edge in board.links if identifier not in (edge.source, edge.target)]
    if previous and state.entry:
        links.append(StoryLink(previous, state.entry))
    if following and state.exit:
        links.append(StoryLink(state.exit, following))
    groups = tuple(replace(group, members=tuple(key for key in group.members if key != identifier))
        for group in board.groups if set(group.members) - {identifier})
    result = replace(board, frames=tuple(frames), links=tuple(links), groups=groups)
    result.validate()
    return result
