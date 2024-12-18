import functools
from types import FunctionType
from typing import Any, Mapping


def match_query(
    value: Mapping[str, Any],
    query: Mapping[str, Any],
) -> bool:
    """Matches query to mapping values.

    :param value: mapping value.
    :param query: pattern to match against value
    """

    match = {key: False for key in query}

    for search_key, search_value in query.items():
        if isinstance(search_value, FunctionType):
            if search_value(value.get(search_key)):
                match[search_key] = True
        else:
            if value.get(search_key) == search_value:
                match[search_key] = True

    if all(match.values()):
        return True

    return False


def locked(f):
    """Decorator for thread-safe methods."""

    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        with self.LOCK:
            return f(self, *args, **kwargs)

    return wrapper
