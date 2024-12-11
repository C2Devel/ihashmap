from typing import Any, Mapping, Optional

import pytest

from ihashmap.cache import Cache, CacheProtocol
from ihashmap.index import Index


class DictCache(CacheProtocol):
    def __init__(self, data: Optional[Mapping[str, Mapping[str, Any]]] = None):
        self.data = data if data is not None else {}

    def get(self, name, key, default=None):
        return self.data.get(name, {}).get(key, default)

    def set(self, name, key, value):
        self.data.setdefault(name, {})[key] = value

    def update(self, name, key, data, fields=None):
        self.data.setdefault(name, {}).setdefault(key, {}).update(data)

    def delete(self, name, key):
        del self.data[name][key]

    def keys(self, name):
        return self.data.get(name, {}).keys()

    def pop(self, name: str, key: str, default: Optional[Any] = None) -> Optional[str]:
        return self.data.get(name, {}).pop(key, default)


@pytest.fixture(autouse=True)
def remove_indexes():
    global_indexes = Index.__INDEXES__.pop("__global__", [])
    Index.__INDEXES__.clear()

    Index.__INDEXES__["__global__"] = global_indexes


@pytest.fixture(autouse=True)
def remove_cache():
    Cache.__INSTANCE__ = None
