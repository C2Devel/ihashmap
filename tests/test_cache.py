from ihashmap.cache import Cache
from ihashmap.index import Index
from tests.conftest import DictCache


def test_Cache_find_all():
    class IndexByModel(Index):
        fields = ["model"]
        cache_name = "test"

    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}
    entity3 = {"_id": "1254", "model": 2, "release": "2.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)
    cache.set("test", entity3)

    assert list(cache.find_all("test")) == [entity1, entity2, entity3]


def test_Cache_search():
    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}
    entity3 = {"_id": "1254", "model": 2, "release": "2.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)
    cache.set("test", entity3)

    assert cache.search("test", {"model": 1}) == [entity1, entity2]
    assert cache.search("test", {"model": 2}) == [entity3]
    assert cache.search("test", {"release": "1.0"}) == [entity1, entity2]
    assert cache.search("test", {"release": "2.0"}) == [entity3]


def test_Cache_search_with_index():
    class IndexByModel(Index):
        fields = ["model"]
        cache_name = "test"

    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}
    entity3 = {"_id": "1254", "model": 2, "release": "2.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)
    cache.set("test", entity3)

    assert cache.search("test", {"model": 1}) == [entity1, entity2]
    assert cache.search("test", {"model": 2}) == [entity3]
    assert cache.search("test", {"release": "1.0"}) == [entity1, entity2]
    assert cache.search("test", {"release": "2.0"}) == [entity3]

    cache.search("test", {"model": lambda v: v in range(5)})


def test_Cache_all():
    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}
    entity3 = {"_id": "1254", "model": 2, "release": "2.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)
    cache.set("test", entity3)

    assert list(cache.all("test")) == [entity1, entity2, entity3]


def test_Cache_delete():
    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}
    entity3 = {"_id": "1254", "model": 2, "release": "2.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)
    cache.set("test", entity3)

    cache.delete("test", entity2["_id"])

    assert cache.get("test", entity2["_id"]) is None
    assert list(cache.all("test")) == [entity1, entity3]


def test_Cache_update():
    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)

    updated_entity1 = {"_id": "1234", "model": 1, "release": "2.0"}
    cache.update("test", updated_entity1)

    assert cache.get("test", entity1["_id"]) == updated_entity1
    assert cache.get("test", entity2["_id"]) == entity2


def test_Cache_get():
    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)

    assert cache.get("test", entity1["_id"]) == entity1
    assert cache.get("test", entity2["_id"]) == entity2
    assert cache.get("test", "nonexistent_id") is None


def test_Cache_set():
    cache = Cache(DictCache())

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1244", "model": 1, "release": "1.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)

    assert cache.get("test", entity1["_id"]) == entity1
    assert cache.get("test", entity2["_id"]) == entity2
