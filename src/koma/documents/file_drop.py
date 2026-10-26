"""Roteamento de projetos soltos, sem importar conteúdo nem trocar sessões."""

from pathlib import Path


def project_drop_path(files):
    if not isinstance(files, list) or any(not isinstance(path, str) or not path for path in files):
        raise ValueError('Lista de arquivos inválida.')
    projects = [Path(path) for path in files if Path(path).suffix.lower() == '.koma']
    if not projects:
        return None
    if len(files) != 1:
        raise ValueError('Solte um projeto .koma por vez, sem misturar com outros arquivos.')
    return projects[0]
