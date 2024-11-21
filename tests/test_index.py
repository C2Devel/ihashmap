import msgpack

from ihashmap.cache import Cache
from ihashmap.index import Index
from tests.conftest import DictCache


def test_Index_get_fields():
    cache = Cache(DictCache())

    class MyIndex(Index):
        fields = ["_id", "model"]
        cache_name = "test"

    index = MyIndex()
    keys = index.get_fields()

    assert isinstance(keys, list), "Expected keys to be a list"
    assert keys == ["_id", "model"], "Expected keys to be ['_id', 'model']"

    class MyIndex2(Index):
        fields = [Index.PK_KEY_PLACEHOLDER, "model"]
        cache_name = "test"

    index = MyIndex2()
    keys = index.get_fields()

    assert isinstance(keys, list), "Expected keys to be a list"
    assert set(keys) == {"_id", "model"}, "Expected keys to be ['_id', 'model']"


def test_Index_cache():
    cache = Cache(DictCache())

    class MyIndex(Index):
        fields = ["_id", "model"]
        cache_name = "test"

    index = MyIndex()

    assert index.cache() is cache, "Expected index cache to be the same as the cache"


def test_Index_get_name():
    cache = Cache(DictCache())

    class MyIndex(Index):
        fields = ["_id", "model"]
        cache_name = "test"

    index = MyIndex()

    assert index.get_name("test") == "_index_:test:_id_model", "Expected index name to be '_index_:test:_id_model'"


def test_Index_get_key():
    cache = Cache(DictCache())

    class MyIndex(Index):
        fields = ["_id", "model"]
        cache_name = "test"

    index = MyIndex()

    entity = {"_id": "1234", "model": 1}
    key = index.get_index_key(entity)

    assert msgpack.loads(key) == {
        "_id": "1234", "model": 1
    }, "Expected key to be {'_id': '1234', 'model': 1}"


def test_Index_append():
    cache = Cache(DictCache())

    class MyIndex(Index):
        fields = ["model"]
        cache_name = "test"

    index = MyIndex()
    entity = {"_id": "1234", "model": 1}
    entity2 = {"_id": "1235", "model": 1}

    cache.set("test", entity)

    index.append("test", entity2)

    assert set(cache.get(index.get_name("test"), index.get_index_key(entity))) == {"1234", "1235"}


def test_Index_cut_data():
    Cache(DictCache())

    class MyIndex(Index):
        fields = ["_id", "model"]
        cache_name = "test"

    index = MyIndex()

    query = {"_id": "1234", "model": 1, "release": "1.0"}
    data = index.cut_data(query)

    assert data == {"_id": "1234", "model": 1}, "Expected data to be {'_id': '1234', 'model': 1}"


def test_Index_remove():
    cache = Cache(DictCache())

    class MyIndex(Index):
        fields = ["model"]
        cache_name = "test"

    index = MyIndex()
    entity = {"_id": "1234", "model": 1}

    cache.set("test", entity)
    index.remove("test", entity)

    assert cache.get(index.get_name("test"), index.get_index_key(entity), []) == []


def test_Index_combine():
    cache = Cache(DictCache())

    class MyIndex(Index):
        fields = ["model"]
        cache_name = "test"

    class MyIndex2(Index):
        fields = ["release"]
        cache_name = "test"

    index = MyIndex()
    index2 = MyIndex2()

    entity1 = {"_id": "1234", "model": 1, "release": "1.0"}
    entity2 = {"_id": "1235", "model": 1, "release": "1.0"}

    cache.set("test", entity1)
    cache.set("test", entity2)

    indexes = [index, index2]
    query = {"_id": "1234", "model": 1, "release": "1.0"}

    data, keys = Index.combine("test", indexes, query)

    assert data == [entity1, entity2]
    assert keys == {"model", "release"}, "Expected keys to be {'release', 'model'}"
