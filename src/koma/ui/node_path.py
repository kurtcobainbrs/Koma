"""Consistent, compact labels derived from the document's node hierarchy."""


def path_text(index, identifier):
    return ' > '.join(node.title or node.node_type.label for node in index.path(identifier))
