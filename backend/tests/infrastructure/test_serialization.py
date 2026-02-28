import msgspec
import pytest

from infrastructure.serialization import clone_with_updates, to_jsonable


class SampleStruct(msgspec.Struct):
    value: int
    name: str = "x"


def test_to_jsonable_struct_and_dict():
    struct_value = SampleStruct(value=3, name="abc")

    assert to_jsonable(struct_value) == {"value": 3, "name": "abc"}
    assert to_jsonable({"x": 1}) == {"x": 1}


def test_clone_with_updates_struct():
    original = SampleStruct(value=1, name="before")

    updated = clone_with_updates(original, {"name": "after"})

    assert isinstance(updated, SampleStruct)
    assert updated.value == 1
    assert updated.name == "after"
    assert original.name == "before"


def test_clone_with_updates_dict():
    original = {"value": 1, "name": "before"}

    updated = clone_with_updates(original, {"name": "after", "extra": True})

    assert updated == {"value": 1, "name": "after", "extra": True}
    assert original == {"value": 1, "name": "before"}


def test_clone_with_updates_unsupported_type_raises():
    with pytest.raises(TypeError):
        clone_with_updates([1, 2, 3], {"value": 9})
