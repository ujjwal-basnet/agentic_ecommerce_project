"""Database row wrappers."""

from __future__ import annotations

import datetime


class Row:
    """Small row wrapper with sqlite.Row-style access by name or index."""

    def __init__(self, columns: list[str], values: tuple):
        self._columns = columns
        self._values = tuple(self._normalize(value) for value in values)
        self._data = dict(zip(columns, self._values))

    @staticmethod
    def _normalize(value):
        if isinstance(value, (datetime.datetime, datetime.date)):
            return value.isoformat()
        return value

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __repr__(self):
        return repr(self._data)
