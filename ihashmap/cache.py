import functools
import logging
import threading
from typing import Any, Callable, Generator, List, Mapping, Optional, Union

from typing_extensions import Protocol, Self, final

from ihashmap.action import Action
from ihashmap.helpers import locked, match_query

LOG = logging.getLogger(__name__)


class CacheProtocol(Protocol):
    """Protocol for cache storage.

    You need to implement locking mechanism in your storage if it is not thread-safe.
    """

    def get(
        self, name: str, key: str, default: Optional[Any] = None
    ) -> Union[Mapping, List[str], str]:
        ...

    def set(self, name: str, key: str, value: Union[Mapping, List[str], str]) -> None:
        ...

    def update(
        self,
        name: str,
        key: str,
        value: Union[Mapping, List[str]],
        fields: Optional[List[str]] = None,
    ) -> None:
        ...

    def delete(self, name: str, key: str) -> None:
        ...

    def keys(self, name: str) -> List[str]:
        ...

    def pop(self, name: str, key: str, default: Optional[Any] = None) -> Optional[str]:
        ...


@final
class PipelineContext:
    def __init__(self, f, cls_or_self, name, *args, **kwargs):
        self.f = f
        self.cls_or_self = cls_or_self
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.local_data = {}


@final
class Pipeline:
    """Class representation of flow process (Middleware pattern).

    Actions are added to be executed before or after main function execution.
    Actions are executed in their insertion order.
    Each pipeline execution has its context which can be useful for storing
    temporary data between actions.
    """

    def __init__(self, name, parent_pipe=None):
        self.name = name
        self.parent_pipe = parent_pipe
        self._pipe_before = []
        self._pipe_after = []

    def pipe_before(self):
        pipe = []
        if self.parent_pipe is not None:
            pipe += self.parent_pipe.pipe_before
        pipe += self._pipe_before
        pipe.sort(key=lambda action: action.priority)
        return pipe

    def pipe_after(self):
        pipe = []

        if self.parent_pipe is not None:
            pipe += self.parent_pipe.pipe_after

        pipe += self._pipe_after
        pipe.sort(key=lambda action: action.priority)

        return pipe

    def before(self, priority=1, cache_name=None):
        def wrapper(f):
            self._pipe_before.append(Action(f, priority, cache_name=cache_name))
            return f

        return wrapper

    def after(self, priority=1, cache_name=None):
        def wrapper(f):
            self._pipe_after.append(Action(f, priority, cache_name=cache_name))
            return f

        return wrapper

    def wrap_before(self, ctx: PipelineContext):
        """Executes all actions in parents _pipe_before and this pipes."""

        for action in self.pipe_before():
            if action.cache_name in [None, ctx.name]:
                action(ctx)

    def wrap_after(self, ctx: PipelineContext):
        """Executes all actions in parents _pipe_after and this pipes."""

        for action in self.pipe_after():
            if action.cache_name in [None, ctx.name]:
                action(ctx)

    def wrap_action(self, ctx: PipelineContext):
        self.wrap_before(ctx)
        ctx.result = ctx.f(ctx.cls_or_self, ctx.name, *ctx.args, **ctx.kwargs)
        self.wrap_after(ctx)
        return ctx.result

    def __call__(self, f: Callable) -> Callable:
        """Wrapper around main function.
        Executes actions before and after main function execution.

        :param f: main function.
        :return: wrapped function.
        """

        @functools.wraps(f)
        def wrap(cls_or_self, name, *args, **kwargs):
            from ihashmap.index import Index

            pipeline = self
            if isinstance(cls_or_self, Cache):
                pipeline = getattr(cls_or_self.PIPELINE, self.name)
            elif isinstance(cls_or_self, Index):
                pipeline = getattr(Cache.PIPELINE, self.name)
            ctx = PipelineContext(f, cls_or_self, name, *args, **kwargs)
            return pipeline.wrap_action(ctx)

        return wrap


@final
class PipelineManager:
    """Manager."""

    def __init__(self, parent_manager=None):
        self.pipes = {}
        if parent_manager is not None:
            self.set_parent(parent_manager)

    def __getattr__(self, item):
        if item not in self.pipes:
            self.pipes[item] = Pipeline(item)
        return self.pipes[item]

    def set_parent(self, parent_manager):
        for pipe_name, pipe in parent_manager.pipes.items():
            self.pipes[pipe_name] = Pipeline(pipe.name, parent_pipe=pipe)


@final
class Cache:
    """Wrapper around user-defined caching storage.

    Adds custom logic to plain hash based storage such as indexes
    and quick search based on them.

    Singleton class.
    """

    PIPELINE = PipelineManager()

    PRIMARY_KEY = "_id"
    """Values primary key existing in all values."""

    __INSTANCE__ = None
    """Singleton instance."""

    LOCK = threading.RLock()
    """Lock for thread-safe operations."""

    def __new__(cls, *args, **kwargs) -> Self:
        """Singleton instance creation."""

        if cls.__INSTANCE__ is None:
            cls.__INSTANCE__ = super().__new__(cls)

        return cls.__INSTANCE__

    def __init__(self, protocol: CacheProtocol) -> None:
        self.protocol = protocol

    def __init_subclass__(cls):
        cls.PIPELINE = PipelineManager(parent_manager=cls.PIPELINE)

        return super().__init_subclass__()

    @classmethod
    def instance(cls):
        return cls.__INSTANCE__

    @PIPELINE.set
    @locked
    def set(self, name: str, entity: Mapping[str, Any]) -> None:
        """Wrapper for pipeline execution.

        :param name: cache name.
        :param entity: stored value.
        """

        if entity.get(self.PRIMARY_KEY) is None:
            raise ValueError(
                f"Primary key {self.PRIMARY_KEY} not found in value: {entity}"
            )

        return self.protocol.set(name, entity[self.PRIMARY_KEY], entity)

    @PIPELINE.get
    def get(self, name: str, key: str, default: Optional[Any] = None):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        :param default: default return value.
        """

        return self.protocol.get(name, key, default)

    @PIPELINE.update
    @locked
    def update(
        self,
        name: str,
        entity: Mapping[str, Any],
        fields: Optional[List[str]] = None,
    ) -> None:
        """Wrapper for pipeline execution.

        :param name: Cache name.
        :param entity: Update entity.
        :param fields: Fields to update. If None, all fields will be updated.
        """

        if entity.get(self.PRIMARY_KEY) is None:
            raise ValueError(
                f"Primary key {self.PRIMARY_KEY} not found in value: {entity}"
            )

        return self.protocol.update(
            name, entity[self.PRIMARY_KEY], entity, fields=fields
        )

    @PIPELINE.delete
    @locked
    def delete(self, name: str, key: str) -> None:
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        """

        return self.protocol.delete(name, key)

    @locked
    def all(self, name: str) -> Generator[Mapping[str, Any], None, None]:
        """Finds all values in cache.

        :param name: cache name.
        """

        for key in self.protocol.keys(name):
            value = self.get(name, key, default=None)
            if value is not None:
                yield value

    @locked
    def search(
        self,
        name: str,
        search_query: Mapping[str, Union[str, int, tuple, list, Callable]],
    ) -> List[Mapping]:
        """Searches cache for required values based on search query.

        :param name: cache name.
        :param dict search_query: search key:value to match.
            Values can be any builtin type or function to which value will be passed as argument.
        :return: list of matching values.
        """

        from ihashmap.index import Index

        index_field_match = []
        indexes = Index.find_index_for_cache(name)

        for index in indexes:
            matched_keys = set(index.get_fields()).intersection(search_query)
            index_field_match.append(matched_keys)

        matching_indexes = sorted(
            filter(lambda x: len(x[1]) > 0, zip(indexes, index_field_match)),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        query_keys = set(search_query.keys())

        hit_indexes = []
        for index, matched_keys in matching_indexes:
            if not query_keys:
                break

            if query_keys.intersection(matched_keys):
                query_keys -= set(matched_keys)
                hit_indexes.append(index)

        matched_pks, combined_keys = Index.combine(
            name,
            hit_indexes,
            search_query,
        )

        rest_query = {
            key: value
            for key, value in search_query.items()
            if key not in combined_keys
        }

        if not hit_indexes:
            LOG.warning(
                "Complete index miss for %s query: %s. Query will be slow.",
                name,
                search_query,
            )

            matched_pks = self.protocol.keys(name)
            rest_query = search_query

        if not rest_query:
            return [self.get(name, pk) for pk in matched_pks]

        result = []
        for pk in matched_pks:
            entity = self.get(name, pk)

            if match_query(entity, rest_query):
                result.append(entity)

        return result

    @locked
    def find_all(self, name: str) -> Generator[Union[Mapping, List[str]], None, None]:
        """Internal method to get all values from cache."""

        for key in self.protocol.keys(name):
            yield self.get(name, key)
