"""Consistent, compact labels derived from the document's node hierarchy."""


def path_text(index, identifier):
    return ' > '.join(index.production.label(node.id) for node in index.path(identifier))
