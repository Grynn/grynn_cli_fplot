"""Named filter presets stored in ~/.config/grynn_fplot/filters.json"""

import json
from pathlib import Path


def get_config_dir() -> Path:
    """Get the config directory for fplot settings."""
    config_dir = Path.home() / ".config" / "grynn_fplot"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_filters_file() -> Path:
    return get_config_dir() / "filters.json"


def load_filters() -> dict[str, str]:
    """Load all saved filters from disk. Returns empty dict if none exist."""
    filters_file = _get_filters_file()
    if not filters_file.exists():
        return {}
    try:
        with open(filters_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _write_filters(filters: dict[str, str]) -> None:
    filters_file = _get_filters_file()
    with open(filters_file, "w") as f:
        json.dump(filters, f, indent=2, sort_keys=True)


def save_filter(name: str, expression: str) -> None:
    """Save a named filter expression. Validates both name and expression."""
    if not name.isidentifier():
        raise ValueError(
            f"Invalid filter name '{name}'. Use alphanumeric characters and underscores, starting with a letter."
        )
    # Validate the expression parses correctly
    from grynn_fplot.filter_parser import parse_filter

    parse_filter(expression)  # raises FilterParseError if invalid

    filters = load_filters()
    filters[name] = expression
    _write_filters(filters)


def delete_filter(name: str) -> bool:
    """Delete a named filter. Returns True if found and deleted."""
    filters = load_filters()
    if name not in filters:
        return False
    del filters[name]
    _write_filters(filters)
    return True


def resolve_filter(filter_value: str) -> str:
    """If filter_value matches a saved name, return its expression.
    Otherwise return filter_value as-is (it's an inline expression)."""
    filters = load_filters()
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


def set_default_filter(name: str | None) -> None:
    """Set (or clear) the default filter name."""
    config = _load_config()
    if name is None:
        config.pop("default_filter", None)
    else:
        # Verify the filter exists
        filters = load_filters()
        if name not in filters:
            raise ValueError(f"Filter '{name}' not found. Save it first with --save-filter.")
        config["default_filter"] = name
    _write_config(config)


def get_default_filter() -> str | None:
    """Get the default filter name, or None if not set."""
    config = _load_config()
    name = config.get("default_filter")
    if name:
        # Verify it still exists
        filters = load_filters()
        if name in filters:
            return name
    return None
