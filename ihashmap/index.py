import threading
from functools import partial
from types import FunctionType
from typing import (Any, Dict, List, Mapping, Optional, Set, Tuple, TypeVar,
                    Union)

import msgpack

from ihashmap.cache import Cache, PipelineContext
from ihashmap.helpers import locked, match_query

T = TypeVar("T")


class Index:
    """Sub-mapping representation that is stored separately for quick search."""

    INDEX_CACHE_PREFIX: str = "_index_"

    # Reverse index is used to quickly find and delete index key by the entity primary key.
    REVERSE_CACHE_INDEX_PREFIX: str = "_reverse_index_"

    KEY_SEPARATOR = "\u00A0"
    PK_KEY_PLACEHOLDER = f"{KEY_SEPARATOR}pk{KEY_SEPARATOR}"

    cache_name: str = None
    """Cache (collection) name for index."""

    fields: List[str]
    """Entity fields in collection stored in index."""

    unique: bool = False
    """Unique index flag."""

    LOCK = threading.Lock()

    __INDEXES__ = {}
    """Storage for all existing indexes."""

    HOOKS = [
        ("before_create", Cache.PIPELINE.set.before),
        ("after_create", Cache.PIPELINE.set.after),
        ("before_get", Cache.PIPELINE.get.before),
        ("after_get", Cache.PIPELINE.get.after),
        ("before_update", Cache.PIPELINE.update.before),
        ("after_update", Cache.PIPELINE.update.after),
        ("before_delete", Cache.PIPELINE.delete.before),
        ("after_delete", Cache.PIPELINE.delete.after),
    ]

    def __init_subclass__(cls):
        """Registers index in global storage."""

        if cls.cache_name is not None:
            cls.__INDEXES__.setdefault(cls.cache_name, []).append(cls)
        else:
            cls.__INDEXES__.setdefault("__global__", []).append(cls)

        cls.fields = list(sorted(set(cls.fields)))

        for hook, pipe_wrapper in cls.HOOKS:
            if hasattr(cls, hook):
                hook_action = getattr(cls, hook)
                setattr(cls, hook, pipe_wrapper(cache_name=cls.cache_name)(hook_action))

    @classmethod
    def get_fields(cls) -> List[str]:
        """Returns index keys with rendered primary key."""

        result = []
        for key in cls.fields:
            result.append(
                key if key != cls.PK_KEY_PLACEHOLDER else cls.cache().PRIMARY_KEY
            )

        return result

    @classmethod
    def cache(cls) -> "Cache":
        """Returns cache instance."""

        return Cache.instance()

    @classmethod
    def get_name(cls, cache_name: str, reverse: bool = False):
        """Composes index name."""

        name = "_".join(cls.get_fields())
        prefix = cls.REVERSE_CACHE_INDEX_PREFIX if reverse else cls.INDEX_CACHE_PREFIX

        return f"{prefix}:{cache_name}:{name}"

    @classmethod
    def get_index_key(cls, value: Mapping[str, Any]) -> str:
        """Returns index key for value.

        :param dict value: cached value.
        :return: str: index in string format.
        """

        return msgpack.dumps(cls.cut_data(value), use_bin_type=False)

    @classmethod
    def cut_data(cls, value: Mapping, exclude_none: bool = False) -> Dict[str, Any]:
        """Cuts data from value for index storage.

        :param dict value: cached value.
        :param bool exclude_none: exclude None values.
        :return: str: index in string format.
        """

        result = {}

        for field in cls.get_fields():
            result[field] = value.get(field)

        return (
            {k: v for k, v in result.items() if v is not None}
            if exclude_none
            else result
        )

    @classmethod
    def before_create(cls, ctx: PipelineContext):
        """Stores original value for after_create usage."""

        value, *_ = ctx.args
        ctx.local_data["value"] = value

        if cls.unique:
            index_key = cls.get_index_key(value)

            if cls.get(ctx.name, index_key):
                raise ValueError(f"Unique index violation {msgpack.loads(index_key, raw=False)}")

    @classmethod
    def after_create(cls, ctx: PipelineContext):
        """Creates index based on pipeline context and creation result.

        :param ctx: PipelineManager context.
        :return:
        """

        cls.append(ctx.name, ctx.local_data["value"])

    @classmethod
    def before_delete(cls, ctx: PipelineContext):
        """Saves cache name for future use in pipeline.

        :param ctx: PipelineManager context.
        """

        ctx.local_data["value"] = cls.cache().protocol.get(ctx.name, ctx.args[0])

    @classmethod
    def after_delete(cls, ctx: PipelineContext):
        """Deletes index based on pipeline context.

        :param dict ctx: PipelineManager context.
        """

        if ctx.local_data["value"]:
            cls.remove(ctx.name, ctx.local_data["value"])

    @classmethod
    def before_update(cls, ctx: PipelineContext):
        """Creates value copy for after_update usage."""

        value, *_ = ctx.args
        ctx.local_data["value"] = cls.cache().protocol.get(ctx.name, value[cls.cache().PRIMARY_KEY])
        if ctx.local_data["value"] is None:
            raise KeyError(f"Entity {value[cls.cache().PRIMARY_KEY]} not found in cache {ctx.name}")

    @classmethod
    def after_update(cls, ctx: PipelineContext):
        """Updates index based on pipeline context.

        :param dict ctx: PipelineManager context.
        """

        cls.remove(ctx.name, ctx.local_data["value"])
        cls.append(ctx.name, ctx.args[0])

    @classmethod
    def find_index_for_cache(cls, cache_name: str) -> List["Index"]:
        """Finds indexes for specific cache name.

        :param str cache_name: cache name.
        :return: list of matching indexes.
        """

        return cls.__INDEXES__.get(cache_name, []) + cls.__INDEXES__.get(
            "__global__", []
        )

    @classmethod
    @Cache.PIPELINE.index_get
    def get(
        cls,
        cache_name: str,
        key: str,
        default: Optional[T] = None,
    ) -> Union[List[str], str, T]:
        return cls.cache().protocol.get(
            cls.get_name(cache_name),
            key,
            default=default,
        )

    @classmethod
    def keys(cls, cache_name: str):
        """Returns all keys for index."""

        return cls.cache().protocol.keys(cls.get_name(cache_name))

    @classmethod
    @Cache.PIPELINE.index_set
    @locked
    def append(cls, cache_name, entity: Mapping[str, Any]) -> None:
        """Appends value to index."""

        index_key = cls.get_index_key(entity)
        value_pk = entity[cls.cache().PRIMARY_KEY]

        current_value = set(cls.get(cache_name, index_key, default=[]))
        current_value.add(value_pk)

        cls.cache().protocol.set(cls.get_name(cache_name), index_key, list(current_value))
        cls.cache().protocol.set(
            cls.get_name(cache_name, reverse=True),
            value_pk,
            index_key,
        )

    @classmethod
    @Cache.PIPELINE.index_delete
    @locked
    def remove(cls, cache_name: str, entity: Mapping[str, Any]) -> None:
        """Removes value from index."""

        entity_pk = entity[cls.cache().PRIMARY_KEY]

        index_key = cls.cache().protocol.pop(
            cls.get_name(cache_name, reverse=True),
            entity_pk,
            default=None,
        )

        if index_key is not None:
            cls.cache().protocol.delete(cls.get_name(cache_name), index_key)

    @classmethod
    def combine(
        cls,
        cache_name: str,
        indexes: List["Index"],
        query: Mapping[str, Any],
    ) -> Tuple[List[str], Set[str]]:
        """Combines indexes into one."""

        combined_index_fields = set()
        matches: List[Mapping[str, Any]] = []

        pk_field = cls.cache().PRIMARY_KEY

        for index in indexes:
            subquery = index.cut_data(query, exclude_none=True)

            combined_index_fields.update(index.get_fields())

            func_search = any(
                isinstance(value, FunctionType) for value in subquery.values()
            )

            if func_search or index.cut_data(query) != subquery:
                index_data = [msgpack.loads(d, raw=False) for d in index.keys(cache_name)]

                for key, value in subquery.items():
                    filter_func = (
                        partial(lambda v, f, k: f(v.get(k)), f=value, k=key)
                        if isinstance(value, FunctionType)
                        else partial(lambda v, t, k: v.get(k) == t, t=value, k=key)
                    )
                    index_data = filter(filter_func, index_data)

                matches.extend(
                    {pk_field: pk_value, **subquery}
                    for i in index_data
                    for pk_value in index.get(cache_name, index.get_index_key(i), default=[])
                )

            else:
                search_key = index.get_index_key(subquery)
                matches.extend(
                    {pk_field: pk_value, **subquery}
                    for pk_value in index.get(cache_name, search_key, default=[])
                )

        combined_index = {}
        for match in matches:
            combined_index.setdefault(match[pk_field], {}).update(match)

        result = []

        indexed_query = {
            key: value for key, value in query.items() if key in combined_index_fields
        }

        for doc in combined_index.values():
            if match_query(doc, indexed_query):
                result.append(doc)

        return (
            sorted(result, key=lambda v: v[pk_field]),
            combined_index_fields,
        )


class PkIndex(Index):
    fields = [Index.PK_KEY_PLACEHOLDER]
    unique = True
