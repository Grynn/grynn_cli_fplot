"""Named filter presets stored in ~/.config/grynn_fplot/filters.json

Storage format:
{
  "calls": {"name": "expression", ...},
  "puts": {"name": "expression", ...}
}
"""

import json
from pathlib import Path


def get_config_dir() -> Path:
    """Get the config directory for fplot settings."""
    config_dir = Path.home() / ".config" / "grynn_fplot"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_filters_file() -> Path:
    return get_config_dir() / "filters.json"


def _load_all() -> dict:
    filters_file = _get_filters_file()
    if not filters_file.exists():
        return {"calls": {}, "puts": {}}
    try:
        with open(filters_file) as f:
            data = json.load(f)
        # Migrate flat format (pre-v0.4.1) to nested format
        if data and "calls" not in data and "puts" not in data:
            data = {"calls": {}, "puts": data}
        data.setdefault("calls", {})
        data.setdefault("puts", {})
        return data
    except (json.JSONDecodeError, IOError):
        return {"calls": {}, "puts": {}}


def _write_all(data: dict) -> None:
    filters_file = _get_filters_file()
    with open(filters_file, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def load_filters(option_type: str) -> dict[str, str]:
    """Load saved filters for the given option type ('calls' or 'puts')."""
    return _load_all().get(option_type, {})


def save_filter(name: str, expression: str, option_type: str) -> None:
    """Save a named filter expression for the given option type."""
    if not name.isidentifier():
        raise ValueError(
            f"Invalid filter name '{name}'. Use alphanumeric characters and underscores, starting with a letter."
        )
    from grynn_fplot.filter_parser import parse_filter

    parse_filter(expression)  # raises FilterParseError if invalid

    data = _load_all()
    data[option_type][name] = expression
    _write_all(data)


def delete_filter(name: str, option_type: str) -> bool:
    """Delete a named filter. Returns True if found and deleted."""
    data = _load_all()
    if name not in data.get(option_type, {}):
        return False
    del data[option_type][name]
    _write_all(data)
    return True


def resolve_filter(filter_value: str, option_type: str) -> str:
    """If filter_value matches a saved name for the option type, return its expression.
    Otherwise return filter_value as-is (it's an inline expression)."""
    filters = load_filters(option_type)
    return filters.get(filter_value, filter_value)


def _get_config_file() -> Path:
    return get_config_dir() / "config.json"


def _load_config() -> dict:
    config_file = _get_config_file()
    if not config_file.exists():
        return {}
    try:
        with open(config_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _write_config(config: dict) -> None:
    config_file = _get_config_file()
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2, sort_keys=True)


def set_default_filter(name: str | None, option_type: str) -> None:
    """Set (or clear) the default filter name for the given option type."""
    config = _load_config()
    key = f"default_filter_{option_type}"
    if name is None:
        config.pop(key, None)
    else:
        filters = load_filters(option_type)
        if name not in filters:
            raise ValueError(f"Filter '{name}' not found in {option_type}. Save it first with --save-filter.")
        config[key] = name
    _write_config(config)


def get_default_filter(option_type: str) -> str | None:
    """Get the default filter name for the given option type, or None if not set."""
    config = _load_config()
    name = config.get(f"default_filter_{option_type}")
    if name:
        filters = load_filters(option_type)
        if name in filters:
            return name
    return None
