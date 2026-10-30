"""Production labels derived from scene/flow order, independent of node titles."""

SCENE_DIGITS = 2
SHOT_DIGITS = 4


def scene_code(number, options=None):
    return production_code('scene', number, options)


def shot_code(number, options=None):
    return production_code('shot', number, options)


def production_code(kind, number, options=None):
    if options is None:
        prefix, digits, suffix = ('Scene_', SCENE_DIGITS, '') if kind == 'scene' else ('shot_', SHOT_DIGITS, '')
    else:
        prefix, digits, suffix = (options[kind + '_prefix'], options[kind + '_digits'], options[kind + '_suffix'])
    return f'{prefix}{number:0{digits}d}{suffix}'


class ProductionNumbers:
    def __init__(self, hierarchy, options=None):
        self.hierarchy = hierarchy
        self.options = options
        self.scenes, self.shots, self.owners = {}, {}, {}
        board = hierarchy.board
        roots = [frame for frame in board.frames if frame.node_type.starts_scene]
        for number, root in enumerate(roots, 1):
            self.scenes[root.id] = number
            key = hierarchy.following.get(root.id)
            while key in hierarchy.nodes and not hierarchy.nodes[key].node_type.starts_scene:
                self.owners[key] = root.id
                for frame in hierarchy.playback(key):
                    if frame.id not in self.shots:
                        self.shots[frame.id] = len(self.shots) + 1
                        self.owners[frame.id] = root.id
                key = hierarchy.following.get(key)
        # Free top-level frames retain useful labels after the numbered scenes.
        # Disconnected members of a group have no role in its production flow.
        for frame in board.frames:
            if frame.id not in hierarchy.parents and frame.id not in self.owners and not frame.node_type.starts_scene:
                for child in hierarchy.playback(frame.id):
                    if child.id not in self.shots:
                        self.shots[child.id] = len(self.shots) + 1

    def code(self, identifier):
        if identifier in self.scenes:
            return scene_code(self.scenes[identifier], self.options)
        if identifier in self.shots:
            return shot_code(self.shots[identifier], self.options)
        return ''

    def label(self, identifier):
        node = self.hierarchy.nodes[identifier]
        code = self.code(identifier)
        title = node.title or ('' if code else node.node_type.label)
        return ' · '.join(part for part in (code, title) if part)
