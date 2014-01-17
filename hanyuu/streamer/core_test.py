from __future__ import absolute_import

from . import core

import pytest


@core.input("tester", bytes)
def test_input_decorator():
    assert test_input_decorator.input_type == bytes
    assert test_input_decorator.input_name == "tester"


@core.output("tester", bytes)
def test_output_decorator():
    assert test_output_decorator.output_type == bytes
    assert test_output_decorator.output_name == "tester"


@core.state
def test_state_decorator():
    assert test_state_decorator.pass_state


def test_state_class():
    """
    Test basic features of State class.

    - Attribute access
    - AttributeError on non-existant attribute
    - mutate method to return a copy
    - equality to other State instances
    """
    state = core.State(hello="World")

    assert state.hello == "World"

    # Test for non-existant keys/attributes
    with pytest.raises(AttributeError):
        state.self

    # Test the mutate method
    new = state.mutate(**{"new": "hello"})

    assert new is not state
    assert state == core.State(hello="World")
    assert new == core.State(hello="World", new="hello")


def test_state_class_immutability():
    """
    Test simple access mutability. The State class is supposed
    to be threated as immutable.

    We check our simple restrictions in this test.
    """
    state = core.State(hello="World")

    # Test for simple mutability
    r = pytest.raises
    r(TypeError, state.__setattr__, "new", "hello")
    r(TypeError, state.__delattr__, "new")
    r(TypeError, state.__setitem__, "new", "hello")
    r(TypeError, state.__delitem__, "new")
    r(TypeError, state.update, {"new": "hello"})
    r(TypeError, state.pop)
    r(TypeError, state.popitem)


def test_extract_arguments_defaults():
    """
    Test _extract_arguments to handle pure defaults.
    """
    function = lambda x=5, y=7, z=10: None

    res = core._extract_arguments(function)

    assert ("x", 5) in res
    assert ("y", 7) in res
    assert ("z", 10) in res


def test_extract_arguments_mixed():
    """
    Test _extract_arguments to handle mixed defaults and nodefaults.
    """
    function = lambda nodefault, hasdefault=True: None

    res = core._extract_arguments(function)

    assert ("hasdefault", True) in res
    assert ("nodefault", core.NoDefaultValue) in res


def test_extract_arguments_nodefaults():
    """
    Test _extract_arguments to handle pure nodefaults.
    """
    function = lambda nodefault, nodefaulteither: None

    res = core._extract_arguments(function)

    assert ("nodefault", core.NoDefaultValue) in res
    assert ("nodefaulteither", core.NoDefaultValue) in res


def test_nodefaultvalue_behaviour():
    assert core.NoDefaultValue == core.NoDefaultValue
    assert core.NoDefaultValue is core.NoDefaultValue
    assert repr(core.NoDefaultValue) == "NoDefaultValue"
    assert isinstance(core.NoDefaultValue, type(core.NoDefaultValue))


def test_consume_simple():
    res = []

    def append_to_res():
        for n in range(10):
            yield res.append(n)

    core.consume(append_to_res())

    assert res == list(range(10))
