"""Catálogo de ações do Storyboard; teclas são padrões, nunca identidade do comando."""

from enum import StrEnum
from koma.keymap import Keymap, ShortcutAction


class Action(StrEnum):
    CLOSE_TAB = 'document.close_tab'
    NEXT_TAB = 'document.next_tab'
    PREVIOUS_TAB = 'document.previous_tab'
    RECENT = 'document.recent'
    COPY = 'nodes.copy'
    CUT_NODES = 'nodes.cut'
    SEARCH = 'nodes.search'
    IMPORT_IMAGES = 'document.import_images'
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
    MUTE = 'storyboard.node.mute'
    INSERT = 'storyboard.insert.menu'
    DUPLICATE = 'storyboard.node.duplicate'
    DELETE = 'storyboard.node.delete'
    GROUP = 'storyboard.node.group'
    SEQUENCE = 'storyboard.node.sequence'
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
    PLAY = 'timeline.play'
    ADD_MARKER = 'timeline.marker.add'
    SNAP = 'timeline.marker.snap'
    PREVIOUS_STOP = 'timeline.previous_stop'
    NEXT_STOP = 'timeline.next_stop'
    PREVIOUS_FRAME = 'timeline.previous_frame'
    NEXT_FRAME = 'timeline.next_frame'
    START = 'timeline.start'
    END = 'timeline.end'
    RENAME_MARKER = 'timeline.marker.rename'
    # Preserve the persisted shortcut id while widening its selection context.
    DELETE_SELECTION = 'timeline.marker.delete'
    DELETE_MARKER = DELETE_SELECTION
    IMPORT_AUDIO = 'timeline.audio.import'
    DRAWING_TOOLS = 'timeline.drawing.tools'
    RIPPLE_DURATION = 'timeline.duration.ripple'


ACTIONS = (
    ShortcutAction(Action.CLOSE_TAB, 'Fechar aba', ('Ctrl+W',)),
    ShortcutAction(Action.NEXT_TAB, 'Próxima aba', ('Ctrl+Tab',)),
    ShortcutAction(Action.PREVIOUS_TAB, 'Aba anterior', ('Ctrl+Shift+Tab',)),
    ShortcutAction(Action.RECENT, 'Abrir recentes', ('Ctrl+Shift+O',)),
    ShortcutAction(Action.COPY, 'Copiar nodes', ('Ctrl+C',)),
    ShortcutAction(Action.CUT_NODES, 'Recortar nodes', ('Ctrl+X',)),
    ShortcutAction(Action.SEARCH, 'Localizar quadros e cenas', ('Ctrl+F',)),
    ShortcutAction(Action.IMPORT_IMAGES, 'Importar imagens', ('Ctrl+I',)),
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
    ShortcutAction(Action.MUTE, 'Mutar/desmutar nodes', ('M',)),
    ShortcutAction(Action.INSERT, 'Inserir', ('Shift+A',)),
    ShortcutAction(Action.DUPLICATE, 'Duplicar', ('Ctrl+D', 'Shift+D')),
    ShortcutAction(Action.DELETE, 'Excluir', ('Delete', 'Backspace')),
    ShortcutAction(Action.GROUP, 'Criar moldura', ('Ctrl+G',)),
    ShortcutAction(Action.SEQUENCE, 'Criar sequência', ('Ctrl+Shift+G',)),
    ShortcutAction(Action.PASTE, 'Colar nodes ou imagem', ('Ctrl+V',)),
    ShortcutAction(Action.UNDO, 'Desfazer', ('Ctrl+Z',), contexts=('canvas', 'timeline')),
    ShortcutAction(Action.REDO, 'Refazer', ('Ctrl+Shift+Z', 'Ctrl+Y'), contexts=('canvas', 'timeline')),
    ShortcutAction(Action.PROPERTIES, 'Propriedades', ('N',), contexts=('canvas', 'timeline')),
    ShortcutAction(Action.FOCUS, 'Enquadrar seleção / timeline', ('F',), contexts=('canvas', 'timeline')),
    ShortcutAction(Action.FIT, 'Enquadrar tudo', ('Home',)),
    ShortcutAction(Action.ALL, 'Selecionar todos', ('A', 'Ctrl+A')),
    ShortcutAction(Action.NONE, 'Limpar seleção', ('Alt+A',)),
    ShortcutAction(Action.CANCEL, 'Cancelar', ('Esc',), contexts=('canvas', 'move', 'timeline')),
    ShortcutAction(Action.CONFIRM, 'Confirmar movimento', ('Enter',), contexts=('move',)),
    ShortcutAction(Action.DETACH, 'Soltar do fluxo ao mover', ('Alt',), contexts=('node_drag',), trigger='modifier'),
    ShortcutAction(Action.ADD_SELECTION, 'Adicionar à seleção', ('Shift',), contexts=('selection',), trigger='modifier'),
    ShortcutAction(Action.SUBTRACT_SELECTION, 'Remover da seleção', ('Ctrl',), contexts=('selection',), trigger='modifier'),
    ShortcutAction(Action.CUT_DRAG, 'Cortar com botão direito', ('Ctrl',), contexts=('wire_drag',), trigger='modifier'),
    ShortcutAction(Action.PLAY, 'Reproduzir / pausar', ('Space',), contexts=('timeline',)),
    ShortcutAction(Action.ADD_MARKER, 'Criar marcador na agulha', ('M',), contexts=('timeline',)),
    ShortcutAction(Action.SNAP, 'Snap de marcadores', ('S',), contexts=('timeline',)),
    ShortcutAction(Action.PREVIOUS_STOP, 'Quadro ou marcador anterior', ('Arrow Up', 'Shift+Arrow Left'), contexts=('timeline',)),
    ShortcutAction(Action.NEXT_STOP, 'Próximo quadro ou marcador', ('Arrow Down', 'Shift+Arrow Right'), contexts=('timeline',)),
    ShortcutAction(Action.PREVIOUS_FRAME, 'Recuar um frame', ('Arrow Left',), contexts=('timeline',)),
    ShortcutAction(Action.NEXT_FRAME, 'Avançar um frame', ('Arrow Right',), contexts=('timeline',)),
    ShortcutAction(Action.START, 'Ir ao início', ('Home',), contexts=('timeline',)),
    ShortcutAction(Action.END, 'Ir ao fim', ('End',), contexts=('timeline',)),
    ShortcutAction(Action.RENAME_MARKER, 'Renomear marcador', ('F2',), contexts=('timeline',)),
    ShortcutAction(Action.DELETE_SELECTION, 'Excluir seleção no animatic', ('Delete',), contexts=('timeline',)),
    ShortcutAction(Action.IMPORT_AUDIO, 'Importar áudio', ('Ctrl+I',), contexts=('timeline',)),
    ShortcutAction(Action.DRAWING_TOOLS, 'Ferramentas de desenho', ('Tab',), contexts=('timeline',)),
    ShortcutAction(Action.RIPPLE_DURATION, 'Empurrar quadros ao ajustar duração', ('Shift',),
        contexts=('duration_drag',), trigger='modifier'),
)


def default_keymap():
    return Keymap(ACTIONS)
