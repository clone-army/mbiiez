"""Validate instance names at the filesystem boundary, including symlinks."""
import re
from pathlib import Path

NAME = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z')


def config_path(name, existing=True):
    from mbiiez import settings
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError('Invalid instance name')
    base = Path(settings.locations.config_path).resolve()
    path = base / (name + '.json')
    if path.is_symlink() or path.resolve().parent != base:
        raise ValueError('Invalid instance path')
    if existing and not path.is_file():
        raise FileNotFoundError('Unknown instance: ' + name)
    return str(path)


def names():
    from mbiiez import settings
    result = []
    for path in Path(settings.locations.config_path).glob('*.json'):
        try:
            config_path(path.stem)
            result.append(path.stem)
        except ValueError:
            pass
    return sorted(result)
