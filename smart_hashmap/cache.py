import copy
import functools
import types
import typing


class Action:
    """Pipeline action representation."""

    def __init__(self, f, cache_name=None):
        self.f = f
        self.cache_name = cache_name

    def execute_before(
        self, ctx: dict, cls: typing.Type["Cache"], *args, **kwargs
    ) -> None:
        """Executes action before main function.

        :param dict ctx: Pipeline context.
        :param type cls: Cache cls.
        :param tuple args: main function args.
        :param dict kwargs: main function kwargs.
        :return: None
        """

        self.f(ctx, cls, *args, **kwargs)

    def execute_after(self, ctx: dict, result: typing.Any) -> typing.Any:
        """Executes function after main function.

        :param dict ctx: Pipeline context.
        :param typing.Any result: main function execution result.
                                  (Can be modified by other actions).
        :return: typing.Any modified/unmodified main function result
        """

        return self.f(ctx, result)


class Pipeline:
    """Class representation of flow process (Middleware pattern).

    Actions are added to be executed before or after main function execution.
    Actions are executed in their insertion order.
    Each pipeline execution has its context which can be useful for storing
    temporary data between actions.
    """

    def __init__(self):
        self.pipe_before = []
        self.pipe_after = []
        self.f = None

    def __call__(self, f: typing.Callable) -> typing.Callable:
        """Wrapper around main function.
        Executes actions before and after main function execution.

        :param f: main function.
        :return: wrapped function.
        """

        self.f = f

        @functools.wraps(f)
        def wrap(cls, name, *args, **kwargs):
            ctx = {}
            for action in self.pipe_before:
                if action.cache_name == name or action.cache_name is None:
                    action.execute_before(ctx, cls, name, *args, **kwargs)
            result = f(cls, name, *args, **kwargs)
            for action in self.pipe_after:
                if action.cache_name == name or action.cache_name is None:
                    result = action.execute_after(ctx, result)
            return result

        return wrap

    def add_action(self, position: str, cache_name: str = None) -> typing.Callable:
        """Decorator for adding action to pipeline.

        :param str position: action placement. Choices: "before"/"after".
        :param str cache_name: Name of cache to apply on. None for all.
        :return: typing.Callable: decorated function untouched.
        """

        def action_wrap(f):
            if position == "before":
                self.pipe_before.append(Action(f, cache_name=cache_name))
            elif position == "after":
                self.pipe_after.append(Action(f, cache_name=cache_name))
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

    PRIMARY_KEY = "_id"
    """Values primary key existing in all values."""

    GET_METHOD = lambda name, key, default=None: None
    SET_METHOD = lambda name, key, value: None
    UPDATE_METHOD = lambda name, key, value: None
    DELETE_METHOD = lambda name, key: None
    """METHODS placeholders. You should register yours."""

    @classmethod
    @PIPELINE_CREATE
    def set(cls, name: str, key: str, value: typing.Mapping):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        :param dict value: stored value.
        :return:
        """

        return cls.SET_METHOD(name, key, value)

    @classmethod
    @PIPELINE_GET
    def get(cls, name: str, key: str, default: typing.Optional[typing.Any] = None):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        :param default: default return value. Must be custom class instance
                        or collections.UserDict/collections.UserList
        :return:
        """

        return cls.GET_METHOD(name, key, default)

    @classmethod
    @PIPELINE_UPDATE
    def update(cls, name: str, key: str, value: typing.Mapping):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        :param dict value: stored value.
        """

        return cls.UPDATE_METHOD(name, key, value)

    @classmethod
    @PIPELINE_DELETE
    def delete(cls, name: str, key: str):
        """Wrapper for pipeline execution.

        :param str name: cache name.
        :param str key: hash key.
        """

        return cls.DELETE_METHOD(name, key)

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

    @classmethod
    def search(
        cls,
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
        index_data = cls.get(name, best_index.get_name())
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
            matched += cls._match_query(value, subquery)
        result = []
        for value in matched:
            entity = cls.get(name, value[cls.PRIMARY_KEY])
            result += cls._match_query(entity, rest_query)
        return result


@Cache.PIPELINE_GET.add_action("after")
def shadow_copy(ctx: dict, result: typing.Any) -> typing.Any:
    """Creates dict copy for future use in pipelines.

    :param dict ctx: Pipeline context.
    :param result: function execution result.
    :return: function result
    """

    result.__shadow_copy__ = copy.copy(result)
    return result