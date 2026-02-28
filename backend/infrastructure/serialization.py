from typing import Any

import msgspec


def to_jsonable(value: Any) -> Any:
    return msgspec.to_builtins(value)


def clone_with_updates(value: Any, updates: dict[str, Any]) -> Any:
    if isinstance(value, msgspec.Struct):
        return msgspec.structs.replace(value, **updates)

    if isinstance(value, dict):
        cloned = dict(value)
        cloned.update(updates)
        return cloned

    raise TypeError(f"Unsupported model type for clone_with_updates: {type(value)!r}")
