"""Atalhos sem dependência de UI: ações estáveis, contextos e remapeamento validado."""

from dataclasses import dataclass
from types import MappingProxyType

MODIFIERS = ('Ctrl', 'Alt', 'Shift', 'Meta')


def key_name(key):
    raw = key.lower().strip()
    aliases = {'': 'Space', 'space': 'Space', 'spacebar': 'Space', 'escape': 'Esc', 'esc': 'Esc',
        'return': 'Enter', 'enter': 'Enter', 'numpad enter': 'Enter', 'delete': 'Delete',
        'backspace': 'Backspace', 'home': 'Home', 'control': 'Ctrl', 'ctrl': 'Ctrl',
        'alt': 'Alt', 'shift': 'Shift', 'meta': 'Meta', 'command': 'Meta', 'super': 'Meta', '+': 'Plus', 'plus': 'Plus',
        'arrowleft': 'Arrow Left', 'arrowright': 'Arrow Right', 'arrowup': 'Arrow Up', 'arrowdown': 'Arrow Down',
        'left': 'Arrow Left', 'right': 'Arrow Right', 'up': 'Arrow Up', 'down': 'Arrow Down'}
    for prefix, name in (('control ', 'Ctrl'), ('ctrl ', 'Ctrl'), ('shift ', 'Shift'),
                         ('alt ', 'Alt'), ('meta ', 'Meta'), ('command ', 'Meta'), ('super ', 'Meta')):
        if raw.startswith(prefix):
            return name
    return aliases.get(raw, raw.upper() if len(raw) == 1 else raw.title())


def normalize(shortcut):
    if not isinstance(shortcut, str) or not shortcut:
        raise ValueError('Informe uma combinação de teclas.')
    parts = [key_name(part) for part in shortcut.split('+')]
    if len(parts) != len(set(parts)) or any(not part.strip() for part in shortcut.split('+')):
        raise ValueError('Combinação de teclas inválida.')
    keys = [part for part in parts if part not in MODIFIERS]
    if len(keys) > 1:
        raise ValueError('Use uma tecla principal por combinação.')
    return '+'.join([part for part in MODIFIERS if part in parts] + keys)


@dataclass(frozen=True)
class ShortcutAction:
    id: str
    label: str
    defaults: tuple[str, ...]
    contexts: tuple[str, ...] = ('canvas',)
    trigger: str = 'press'  # press, hold ou modifier (gesto com mouse).


class Keymap:
    def __init__(self, actions):
        definitions = tuple(actions)
        self.actions = MappingProxyType({action.id: action for action in definitions})
        if len(self.actions) != len(definitions):
            raise ValueError('Há identificadores de ações repetidos.')
        if any(not action.id or not action.contexts or action.trigger not in ('press', 'hold', 'modifier') for action in definitions):
            raise ValueError('Definição de ação de atalho inválida.')
        self.overrides = {}
        self.listeners = []
        self.configure({})

    def bindings(self, action):
        return self.overrides.get(action, tuple(normalize(value) for value in self.actions[action].defaults))

    def label(self, action):
        bindings = self.bindings(action)
        return bindings[0] if bindings else ''

    def describe(self, title, action):
        shortcut = self.label(action)
        return f'{title} · {shortcut}' if shortcut else title

    def configure(self, overrides):
        """Aplica um conjunto inteiro atomicamente; permite trocar dois atalhos entre si."""
        if not isinstance(overrides, dict) or set(overrides) - self.actions.keys():
            raise ValueError('Ação de atalho desconhecida.')
        candidate = {}
        for action, values in overrides.items():
            if not isinstance(values, (tuple, list)):
                raise ValueError('Os atalhos devem ser uma lista de combinações.')
            candidate[action] = tuple(dict.fromkeys(normalize(value) for value in values))
        occupied = {}
        for action in self.actions.values():
            for combo in candidate.get(action.id, tuple(normalize(value) for value in action.defaults)):
                if action.trigger == 'modifier' and any(key not in MODIFIERS for key in combo.split('+')):
                    raise ValueError(f'{action.label} exige uma tecla modificadora.')
                if action.trigger == 'press' and all(key in MODIFIERS for key in combo.split('+')):
                    raise ValueError(f'{action.label} exige uma tecla principal.')
                for context in action.contexts:
                    previous = occupied.get((context, combo))
                    if previous and previous != action.id:
                        raise ValueError(f'{combo}: conflito entre {self.actions[previous].label} e {action.label}.')
                    occupied[context, combo] = action.id
        self.overrides = candidate
        for listener in tuple(self.listeners):
            listener()

    def rebind(self, action, bindings):
        self.configure({**self.overrides, action: bindings})

    def reset(self, action=None):
        self.configure({key: value for key, value in self.overrides.items() if key != action} if action else {})

    def resolve(self, key, modifiers=(), context='canvas'):
        name = key_name(key)
        combo = normalize('+'.join([part for part in MODIFIERS if part in modifiers and part != name] + [name]))
        return next((action.id for action in self.actions.values() if action.trigger != 'modifier'
            and context in action.contexts and combo in self.bindings(action.id)), None)

    def modifier_active(self, action, modifiers):
        return any(set(combo.split('+')) <= set(modifiers) for combo in self.bindings(action))

    def export(self):
        return {'version': 1, 'bindings': {key: list(value) for key, value in self.overrides.items()}}

    def restore(self, data):
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Preferências de atalhos inválidas.')
        self.configure(data.get('bindings', {}))
