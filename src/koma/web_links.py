"""Web address validation shared by stored links, editing and browser actions."""
from urllib.parse import urlsplit

MAX_WEB_LINK_LENGTH = 4096
WEB_SCHEMES = frozenset(('http', 'https'))


def web_link(value):
    if not isinstance(value, str) or len(value) > MAX_WEB_LINK_LENGTH:
        raise ValueError(f'O link deve ter até {MAX_WEB_LINK_LENGTH} caracteres.')
    value = value.strip()
    if not value:
        return ''
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError('Informe um link sem espaços.')
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in WEB_SCHEMES or not parsed.hostname or parsed.port == 0:
            raise ValueError
        if '\\' in parsed.netloc:
            raise ValueError
    except ValueError:
        raise ValueError('Informe um link completo com https:// ou http://.') from None
    return value
