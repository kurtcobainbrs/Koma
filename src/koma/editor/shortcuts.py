"""Catálogo de ações do Storyboard; teclas são padrões, nunca identidade do comando."""

from enum import StrEnum
from koma.keymap import Keymap, ShortcutAction


class Action(StrEnum):
    NEW = 'document.new'
    OPEN = 'document.open'
    SAVE = 'document.save'
    SAVE_AS = 'document.save_as'
    SELECT = 'storyboard.tool.select'
    PAN = 'storyboard.tool.pan'
    ZOOM = 'storyboard.tool.zoom'
    CUT = 'storyboard.tool.cut'
    TEMP_PAN = 'storyboard.pan.temporary'
    MOVE = 'storyboard.node.move'
    DUPLICATE = 'storyboard.node.duplicate'
    DELETE = 'storyboard.node.delete'
    GROUP = 'storyboard.node.group'
    PASTE = 'storyboard.image.paste'
    UNDO = 'storyboard.undo'
    REDO = 'storyboard.redo'
    PROPERTIES = 'storyboard.properties.toggle'
    FOCUS = 'storyboard.view.focus'
    FIT = 'storyboard.view.fit'
    ALL = 'storyboard.selection.all'
    NONE = 'storyboard.selection.none'
    CANCEL = 'storyboard.cancel'
    CONFIRM = 'storyboard.move.confirm'
    DETACH = 'storyboard.drag.detach'
    ADD_SELECTION = 'storyboard.selection.add'
    SUBTRACT_SELECTION = 'storyboard.selection.subtract'
    CUT_DRAG = 'storyboard.wire.cut_drag'


ACTIONS = (
    ShortcutAction(Action.NEW, 'Novo documento', ('Ctrl+N',)),
    ShortcutAction(Action.OPEN, 'Abrir documento', ('Ctrl+O',)),
    ShortcutAction(Action.SAVE, 'Salvar documento', ('Ctrl+S',)),
    ShortcutAction(Action.SAVE_AS, 'Salvar como', ('Ctrl+Shift+S',)),
    ShortcutAction(Action.SELECT, 'Seleção', ('V',)),
    ShortcutAction(Action.PAN, 'Pan', ('H',)),
    ShortcutAction(Action.ZOOM, 'Zoom por caixa', ('Z',)),
    ShortcutAction(Action.CUT, 'Cortar ligações', ('K',)),
    ShortcutAction(Action.TEMP_PAN, 'Pan temporário', ('Space',), trigger='hold'),
    ShortcutAction(Action.MOVE, 'Mover', ('G',)),
    ShortcutAction(Action.DUPLICATE, 'Duplicar', ('Shift+D',)),
    ShortcutAction(Action.DELETE, 'Excluir', ('Delete', 'Backspace')),
    ShortcutAction(Action.GROUP, 'Criar moldura', ('Ctrl+G',)),
    ShortcutAction(Action.PASTE, 'Colar imagem', ('Ctrl+V',)),
    ShortcutAction(Action.UNDO, 'Desfazer', ('Ctrl+Z',)),
    ShortcutAction(Action.REDO, 'Refazer', ('Ctrl+Shift+Z', 'Ctrl+Y')),
    ShortcutAction(Action.PROPERTIES, 'Propriedades', ('N',)),
    ShortcutAction(Action.FOCUS, 'Enquadrar seleção', ('F',)),
    ShortcutAction(Action.FIT, 'Enquadrar tudo', ('Home',)),
    ShortcutAction(Action.ALL, 'Selecionar todos', ('A',)),
    ShortcutAction(Action.NONE, 'Limpar seleção', ('Alt+A',)),
    ShortcutAction(Action.CANCEL, 'Cancelar', ('Esc',), contexts=('canvas', 'move')),
    ShortcutAction(Action.CONFIRM, 'Confirmar movimento', ('Enter',), contexts=('move',)),
    ShortcutAction(Action.DETACH, 'Soltar do fluxo ao mover', ('Alt',), contexts=('node_drag',), trigger='modifier'),
    ShortcutAction(Action.ADD_SELECTION, 'Adicionar à seleção', ('Shift',), contexts=('selection',), trigger='modifier'),
    ShortcutAction(Action.SUBTRACT_SELECTION, 'Remover da seleção', ('Ctrl',), contexts=('selection',), trigger='modifier'),
    ShortcutAction(Action.CUT_DRAG, 'Cortar com botão direito', ('Ctrl',), contexts=('wire_drag',), trigger='modifier'),
)


def default_keymap():
    return Keymap(ACTIONS)
