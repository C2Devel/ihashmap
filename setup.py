#!/usr/bin/env python

import setuptools

module_info = {
    "name": "ihashmap",
    "version": "1.1",
    "description": "Wrapper for hash map based storage systems",
    "author": "Yury Sokov aka. Yurzs",
    "author_email": "me@yurzs.dev",
    "packages": setuptools.find_packages(
        exclude=("tests", "tests.*", "*.tests"),
    ),
    "license": "MIT",
    "keywords": ["cache", "indexes"],
    "url": "https://github.com/yurzs/smart_hashmap",
    "classifiers": [
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
}

with open("README.rst") as long_description_file:
    module_info["long_description"] = long_description_file.read()

setuptools.setup(**module_info)
