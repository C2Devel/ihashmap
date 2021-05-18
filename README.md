Smart Hashmap
===========

[![Lint and test](https://github.com/Yurzs/smart_hashmap/actions/workflows/python-on-pull-request.yml/badge.svg)](https://github.com/Yurzs/smart_hashmap/actions/workflows/python-on-pull-request.yml)

![Smart Hashmap](https://raw.github.com/yurzs/smart_hashmap/master/assets/hashmap-logo.svg)

Wrapper for key-value based storage systems. Provides convenient way to organize data for quick searching.

Installation
------------

1. Using pip:  
`pip install smart_hashmap`
   
2. Building from source:  
`make install`
   
How to use
----------

Firstly you need to register methods:

```python3
from smart_hashmap.cache import Cache

Cache.register_get_method(YOUR_GET_METHOD)
Cache.register_set_method(YOUR_SET_METHOD)
Cache.register_update_method(YOUR_UPDATE_METHOD)
Cache.register_delete_method(YOUR_DELETE_METHOD)
```

NOTE: Methods signature MUST match their placeholders signature

```python3
GET_METHOD = lambda cache, name, key, default=None: None  # noqa: E731
SET_METHOD = lambda cache, name, key, value: None  # noqa: E731
UPDATE_METHOD = lambda cache, name, key, value: None  # noqa: E731
DELETE_METHOD = lambda cache, name, key: None  # noqa: E731
"""METHODS placeholders. You should register yours."""
```

Now you are all set up to use `Cache.search`

How it works
------------

In default setup `Cache` creates and maintains indexes based on `Cache.primary_key`.  
So every object save in cache MUST have such key. (By default its `_id`)

On every called action for example `Cache.update` 
Cache looks in pipeline `Cache.PIPELINE.update` for middlewares to run before and after main function execution.
For example in current situation after `.update` function execution indexing middleware will
check if documents fields matching its keys were changed.  
If so it will get index data, look for old values in `value.__shadow_copy__` 
remove such index data and create new record with updated values.

Adding middlewares
------------------

Adding new action is easy:

```python3
from smart_hashmap.cache import Cache, PipelineContext

@Cache.PIPELINE.set.before()
def add_my_field(ctx: PipelineContext):
    
    key, value = ctx.args
    value["my_field"] = 1

```

Now every cache value saved with `Cache.set` will be added `'my_field'` 
before main function execution.

Custom Indexes
--------------

To create custom index you need to simply create new subclass of Index.

```python3
from smart_hashmap.index import Index

class IndexByModel(Index):
    keys = ["_id", "model"]
```

NOTE: After that all values MUST have fields `_id` AND `model`  
NOTE: Primary key MUST ALWAYS be in `keys`

Searching 
---------

After all required indexes created - searching will be as quick as possible.

```python3
from smart_hashmap.cache import Cache
from smart_hashmap.index import Index

class IndexByModel(Index):
    keys = ["_id", "model"]


cache = Cache()
cache.search("my_cache", {"model": "1.0"})
```

When `.search` is called it will firstly check for indexes containing search fields.  
After finding best index, it will get index data and find matching primary keys.
Now searching is as easy as getting values by their key.