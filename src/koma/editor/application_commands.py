"""Document shortcuts remain available while text inputs own keyboard focus."""

from koma.editor.shortcuts import Action

DOCUMENT_ACTIONS = frozenset((Action.NEW, Action.OPEN, Action.SAVE, Action.SAVE_AS,
    Action.CLOSE_TAB, Action.NEXT_TAB, Action.PREVIOUS_TAB, Action.RECENT, Action.SEARCH))


async def dispatch(application, e):
    modifiers = {name for field, name in (('ctrl', 'Ctrl'), ('alt', 'Alt'), ('shift', 'Shift'), ('meta', 'Meta'))
        if getattr(e, field, False)}
    view = application.view
    action = view.keymap.resolve(e.key, modifiers, 'canvas')
    if action not in DOCUMENT_ACTIONS:
        return False
    if application.transitioning or application.closing_attempt or any(v.busy for v in application.views):
        return True
    handlers = {Action.NEW: application.new_document, Action.OPEN: view.files.open_document,
        Action.SAVE: view.files.save_document, Action.SAVE_AS: view.files.save_as,
        Action.CLOSE_TAB: lambda: application.close_tab(view),
        Action.NEXT_TAB: lambda: application.select_view(application.views[(application.views.index(view) + 1) % len(application.views)]),
        Action.PREVIOUS_TAB: lambda: application.select_view(application.views[(application.views.index(view) - 1) % len(application.views)])}
    if action == Action.RECENT:
        application.document_tools.recent()
    elif action == Action.SEARCH:
        application.document_tools.search()
    else:
        await handlers[action]()
    return True
