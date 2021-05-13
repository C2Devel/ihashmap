import collections
import copy
import functools
import types
import typing


class Action:
    """Pipeline action representation."""

    def __init__(self, f, cache_name=None):
        self.f = f
        self.cache_name = cache_name

    def execute_before(self, ctx: "PipelineContext") -> None:
        """Executes action before main function.

        :param dict ctx: Pipeline context.
        :return: None
        """

        self.f(ctx)

    def execute_after(self, ctx: "PipelineContext") -> None:
        """Executes function after main function.

        :param dict ctx: Pipeline context.
        :return: typing.Any modified/unmodified main function result
        """

        return self.f(ctx)


class PipelineContext:
    def __init__(self, f, cls_or_self, name, *args, **kwargs):
        self.f = f
        self.cls_or_self = cls_or_self
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.local_data = {}


class Pipeline:
    """Class representation of flow process (Middleware pattern).

    Actions are added to be executed before or after main function execution.
    Actions are executed in their insertion order.
    Each pipeline execution has its context which can be useful for storing
    temporary data between actions.
    """

    def __init__(self, parent_pipeline=None):
        self.pipe_before = []
        self.pipe_after = []
        self.f = None
        self.parent_pipeline: Pipeline = parent_pipeline

    def wrap_before(self, ctx: PipelineContext):
        """Executes all actions in parents pipe_before and this pipes."""

        for action in self.pipe_before:
            if action.cache_name == ctx.name or action.cache_name is None:
                action.execute_before(ctx)

    def wrap_after(self, ctx: PipelineContext):
        """Executes all actions in parents pipe_after and this pipes."""

        for action in self.pipe_after:
            if action.cache_name == ctx.name or action.cache_name is None:
                action.execute_after(ctx)

    def wrap_action(self, ctx: PipelineContext):
        if self.parent_pipeline is not None:
            self.parent_pipeline.wrap_before(ctx)
        self.wrap_before(ctx)
        ctx.result = self.f(ctx.cls_or_self, ctx.name, *ctx.args, **ctx.kwargs)
        if self.parent_pipeline is not None:
            self.parent_pipeline.wrap_after(ctx)
        self.wrap_after(ctx)
        return ctx.result

    def __call__(self, f: typing.Callable) -> typing.Callable:
        """Wrapper around main function.
        Executes actions before and after main function execution.

        :param f: main function.
        :return: wrapped function.
        """

        self.f = f

        @functools.wraps(f)
        def wrap(cls, name, *args, **kwargs):
            ctx = PipelineContext(self.f, cls, name, *args, **kwargs)
            return self.wrap_action(ctx)

        return wrap

    def add_action(
        self, position: str, cache_name: str = None, pipe_position=-1
    ) -> typing.Callable:
        """Decorator for adding action to pipeline.

        :param str position: action placement. Choices: "before"/"after".
        :param str cache_name: Name of cache to apply on. None for all.
        :param pipe_position: specify position in pipe to push to. Last by default (-1).
        :return: typing.Callable: decorated function untouched.
        """

        def action_wrap(f):

            if position == "before":
                insert_position = (
                    len(self.pipe_before) - pipe_position + 1
                    if pipe_position < 0
                    else pipe_position
                )
                self.pipe_before.insert(
                    insert_position, Action(f, cache_name=cache_name)
                )
            elif position == "after":
                insert_position = (
                    len(self.pipe_after) - pipe_position + 1
                    if pipe_position < 0
                    else pipe_position
                )
                self.pipe_after.insert(
                    insert_position, Action(f, cache_name=cache_name)
                )
            return f

        return action_wrap


class Cache:
    """Wrapper around user-defined caching storage.

    Adds custom logic to plain hash based storage such as indexes
    and quick search based on them.

    For usage first define GET_METHOD, SET_METHOD, UPDATE_METHOD, DELETE_METHOD
    with matching signatures using `register_*` methods.
    Secondly create required indexes (pk index is required by default).
    """

    PIPELINE_GET = Pipeline()
    PIPELINE_CREATE = Pipeline()
    PIPELINE_UPDATE = Pipeline()
    PIPELINE_DELETE = Pipeline()
    PIPELINE_INDEX_GET = Pipeline()
    PIPELINE_INDEX_SET = Pipeline()

    PRIMARY_KEY = "_id"
    """Values primary key existing in all values."""

    GET_METHOD = lambda cache, name, key, default=None: None
    SET_METHOD = lambda cache, name, key, value: None
    UPDATE_METHOD = lambda cache, name, key, value: None
    DELETE_METHOD = lambda cache, name, key: None
    """METHODS placeholders. You should register yours."""

    @PIPELINE_CREATE
    def set(self, name: str, key: str, value: typing.Mapping):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        :param dict value: stored value.
        :return:
        """

        return self.SET_METHOD(name, key, value)

    @PIPELINE_GET
    def get(self, name: str, key: str, default: typing.Optional[typing.Any] = None):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        :param default: default return value. Must be custom class instance
                        or collections.UserDict/collections.UserList
        :return:
        """

        return self.GET_METHOD(name, key, default)

    @PIPELINE_UPDATE
    def update(self, name: str, key: str, value: typing.Mapping):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        :param dict value: stored value.
        """

        return self.UPDATE_METHOD(name, key, value)

    @PIPELINE_DELETE
    def delete(self, name: str, key: str):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        """

        return self.DELETE_METHOD(name, key)

    def all(self, name: str):
        """Finds all values in cache.

        :param name:
        :return:
        """

        index_name = f"index:{self.PRIMARY_KEY}"

        index_data = self._get(name, index_name, default=collections.UserList())
        result = []
        for item_key in index_data:
            result.append(self._get(name, item_key))
        return result

    @classmethod
    def register_get_method(cls, method: typing.Callable):
        """Registers get method for global cache usage.

        :param method: function which will be called on .get method execution
        """

        cls.GET_METHOD = method

    @classmethod
    def register_set_method(cls, method: typing.Callable):
        """Registers set method for global cache usage.

        :param method: function which will be called on .set method execution.
        """

        cls.SET_METHOD = method

    @classmethod
    def register_update_method(cls, method: typing.Callable):
        """Registers update method for global cache usage.

        :param method: function which will be called on .update method execution.
        """

        cls.UPDATE_METHOD = method

    @classmethod
    def register_delete_method(cls, method: typing.Callable):
        """Registers update method for global cache usage.

        :param method: function which will be called on .delete method execution.
        :return:
        """
        cls.DELETE_METHOD = method

    @classmethod
    def _match_query(cls, value: dict, query: dict):
        """Matches query to mapping values.

        :param value: value to match against pattern
        :param query: dict se
        :return:
        """

        matched = []
        match = {key: False for key in query}
        for search_key, search_value in query.items():
            if isinstance(search_value, types.FunctionType):
                if search_value(value.get(search_key)):
                    match[search_key] = True
            else:
                if value.get(search_key) == search_value:
                    match[search_key] = True
        if all(match.values()):
            matched.append(value)
        return matched

    def search(
        self,
        name: str,
        search_query: typing.Mapping[
            str, typing.Union[str, int, tuple, list, typing.Callable]
        ],
    ) -> typing.List[typing.Mapping]:
        """Searches cache for required values based on search query.

        :param name: cache name.
        :param dict search_query: search key:value to match.
                                  Values can be any builtin type
                                  or function to which value will be passed as argument.
        :return: list of matching values.
        """

        from smart_hashmap.index import Index

        index_match = []
        indexes = Index.find_index_for_cache(name)
        for index in indexes:
            index_match.append(
                len(set(index.keys).intersection(search_query)) / len(search_query)
            )
        best_choice_index = index_match.index(max(index_match))
        best_index = indexes[best_choice_index]
        index_data = set(best_index.get(name))
        index_data = best_index.get_values(index_data)
        matched = []
        subquery = {
            key: value for key, value in search_query.items() if key in best_index.keys
        }
        rest_query = {
            key: value
            for key, value in search_query.items()
            if key not in best_index.keys
        }
        for value in index_data:
            matched += self._match_query(value, subquery)
        result = []
        for value in matched:
            entity = self._get(name, value[self.PRIMARY_KEY])
            result += self._match_query(entity, rest_query)
        return result

    @PIPELINE_GET
    def _get(self, name: str, key: str, default: typing.Optional[typing.Any] = None):
        """Internal method. PLEASE DONT CHANGE!"""

        return self.GET_METHOD(name, key, default)

    @PIPELINE_CREATE
    def _set(self, name, key, value):
        """Internal method. PLEASE DONT CHANGE!"""

        return self.SET_METHOD(name, key, value)

    @PIPELINE_UPDATE
    def _update(self, name, key, value):
        """Internal method. PLEASE DONT CHANGE!"""

        return self.UPDATE_METHOD(name, key, value)

    @PIPELINE_DELETE
    def _delete(self, name, key):
        """Internal method. PLEASE DONT CHANGE!"""

        return self.DELETE_METHOD(name, key)

    def __init_subclass__(cls, **kwargs):
        for attr_name in dir(cls):
            if attr_name.startswith("PIPELINE_"):
                setattr(
                    cls, attr_name, Pipeline(parent_pipeline=getattr(cls, attr_name))
                )


@Cache.PIPELINE_GET.add_action("after")
def shadow_copy(ctx: PipelineContext) -> typing.Any:
    """Creates dict copy for future use in pipelines.

    :param dict ctx: Pipeline context.
    :return: function result
    """

    ctx.result.__shadow_copy__ = copy.copy(ctx.result)
