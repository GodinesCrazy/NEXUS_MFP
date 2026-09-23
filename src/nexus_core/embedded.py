"""Safe helpers for executing the legacy embedded one-file chain."""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def registered_module(name: str) -> Iterator[types.ModuleType]:
    """Temporarily register a synthetic module required by ``dataclass``.

    Historical one-file versions execute source with ``exec`` and assign a
    synthetic ``__name__``. Python 3.10's dataclass machinery expects that
    name to exist in ``sys.modules``. The historical files remain untouched;
    the active entrypoint supplies the missing runtime contract.
    """

    previous = sys.modules.get(name)
    module = types.ModuleType(name)
    module.__file__ = f"<embedded:{name}>"
    sys.modules[name] = module
    try:
        yield module
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
