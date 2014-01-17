from __future__ import absolute_import

from . import core

import pytest


def generator(type):
    @core.input("string")
    @core.output("string")
    def lower_generator(pipe):
        for string in pipe:
            yield string.lower()


    @core.input("integer", type=int)
    @core.output("integer", type=int)
    def range_generator(pipe, n=100):
        pipe = pipe or [n]

        for n in pipe:
            for x in range(n):
                yield x


    @core.input("integer", type=int)
    @core.output("integer", type=int)
    @core.state
    def state_setter_generator(pipe):
        for state, data in pipe:
            state = core.State(tester=data)
            yield state, data


    @core.input("integer", type=int)
    @core.output("integer", type=int)
    @core.state
    def state_getter_generator(pipe):
        for state, data in pipe:
            assert 0 < state.tester < 100

            yield state, data



    if type == "range":
        return range_generator
    elif type == "lower":
        return lower_generator
    elif type == "plain":
        return plain_generator
    elif type == "state_setter":
        return state_setter_generator
    elif type == "state_getter":
        return state_getter_generator


@pytest.fixture
def range_generator():
    return generator('range')


@pytest.fixture
def lower_generator():
    return generator('lower')


@pytest.fixture
def plain_generator():
    return generator('plain')


@pytest.fixture
def valid_pipeline():
    return [generator('range'), generator('range')]


@pytest.fixture
def invalid_pipeline():
    return [generator('range'), generator('lower')]


@pytest.fixture
def state_pipeline():
    return [generator('range'), generator('state_setter'),
            generator('range'), generator('range'),
            generator('state_getter'), generator('range')]