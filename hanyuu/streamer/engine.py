from __future__ import absolute_import

import functools
from . import core

class DefaultName(object):
    pass


default_pipe_variables = {
    'output_name': DefaultName(),
    'input_name' : DefaultName(),
    'output_type': None,
    'input_type' : None,
    'pass_state' : False,
}


class PipeError(Exception):
    def __init__(self, string, *args, **kwargs):
        super(PipeError, self).__init__(string.format(*args, **kwargs))


def verify_pipe_types(pipes):
    """
    Verifies that all pipes have the correct input/output type according
    to their neighbours in the pipeline.

    raises `PipeError` if an incompatiblity is found.
    """
    attributes_to_check = (
        ("output_type", "input_type"),
        ("output_name", "input_name"),
    )

    previous_pipe = pipes[0]
    for pipe in pipes[1:]:
        for out_attr, in_attr in attributes_to_check:

            out_attr_value = getattr(previous_pipe, out_attr)
            in_attr_value = getattr(pipe, in_attr)

            if out_attr_value != in_attr_value:
                raise PipeError(
                    "Incompatible output/input found: "
                    "(output: {:s} from {:s}) (input: {:s} to {:s})",
                    out_attr_value, previous_pipe.__name__,
                    in_attr_value, pipe.__name__)

        previous_pipe = pipe


def initialize_pipe_variables(pipe):
    """
    Sets all possible attributes on a pipe function to their
    default value.

    Does not touch attributes already set
    """
    for attribute, default in default_pipe_variables.iteritems():
        setattr(pipe, attribute, getattr(pipe, attribute, default))


def initialize_pipeline_state_handling(pipes):
    first_pipe = pipes[0]

    stated_pipes = []
    if not first_pipe.pass_state:
        stated_pipes.append(_create_state(first_pipe))

    for pipe in pipes[1:]:
        if pipe.pass_state:
            stated_pipes.append(pipe)
        else:
            stated_pipes.append(_skip_state(pipe))

    return stated_pipes


def pipeline(*pipeline):
    for pipe in pipeline:
        initialize_pipe_variables(pipe)

    verify_pipe_types(pipeline)

    pipeline = initialize_pipeline_state_handling(pipeline)

    return reduce(lambda next, current: current(next), pipeline, None)


def _skip_state(to_be_wrapped):
    last_state = [None]
    def remove_state(pipe):
        for state, data in pipe:
            last_state[0] = state
            yield data

    def add_state(pipe):
        for data in pipe:
            yield last_state[0], data

    @functools.wraps(to_be_wrapped)
    def skipper(pipe, *args, **kwargs):
        removal = remove_state(pipe)

        wrapped = to_be_wrapped(removal, *args, **kwargs)

        return add_state(wrapped)

    return skipper


def _create_state(to_be_wrapped):
    @functools.wraps(to_be_wrapped)
    def creator(pipe, *args, **kwargs):
        for data in to_be_wrapped(pipe, *args, **kwargs):
            yield core.State(), data

    return creator