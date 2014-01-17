from __future__ import absolute_import

from . import util

import functools
import collections
import inspect


def input(name, type=None):
    """
    Specifies the input type expected by the generator. This is used
    to check compatiblity of pipes at pipeline creation.
    """
    def input(function):
        function.input_type = type
        function.input_name = name
        return function
    return input


def output(name, type=None):
    """
    Specifies the output type of the generator. This is used
    to check compatibility of pipes at pipeline creation.
    """
    def output(function):
        function.output_type = type
        function.output_name = name
        return function
    return output


def state(function):
    """
    Specifies that the decorated generator wants a state
    variable to be passed along with the result from the
    previous generator in the pipeline.

    This changes the `pipe` iterator to return (state, data)
    tuples.

    `state` can be None if no state was previously set for
    this piece of data.
    """
    function.pass_state = True
    return function


def config(name=None, redirect=None, only_with_defaults=False, without=None):
    def config(function):
        function.redirected_configuration = redirect

        to_read_config = function

        # Resolve the redirection chain.
        while getattr(to_read_config, "redirected_configuration", None):
            to_read_config = getattr(to_read_config, "redirected_configuration")

        possible_arguments = _extract_arguments(to_read_config)

        if only_with_defaults:
            # Remove any arguments that don't have a default value
            possible_arguments = [(arg, default) for arg, default in
                                  possible_arguments if default is not NoDefaultValue]

        if without:
            # Remove any arguments that were explicitely marked as to be
            # not used by the `without` argument.
            possible_arguments = [(arg, default) for arg, default in
                                  possible_arguments if (arg not in without)]

        if name:
            # Prepend all the arguments with our configuration name to avoid
            # name collision, and make it clearer to the configuration writer
            # where each option goes.
            possible_arguments = [('.'.join((name, arg)), default) for arg, default
                                  in possible_arguments]

        function.config_name   = name
        function.configuration = possible_arguments

        return function
    return config



def consume(generator):
    """
    Consumes a generator fully. Returns no result.

    Any exceptions are propagated.
    """
    d = collections.deque(maxlen=0)
    d.extend(generator)


class State(dict):
    """
    An immutable dictionary, keys can only be set at creation.
    """
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return super(State, self).__getattr__(key)

    def mutate(self, **kwargs):
        """
        Updates a copy of self and returns it.

        This is about equal to the following code:
            copied = self.copy()
            copied.update(kwargs)
            return copied
        """
        c = self.copy()
        c.update(kwargs)
        return type(self)(c)

    def raise_type_error(self, *args, **kwargs):
        raise TypeError("State object can't be mutated")

    __setattr__ = raise_type_error
    __delattr__ = raise_type_error
    __setitem__ = raise_type_error
    __delitem__ = raise_type_error
    update      = raise_type_error
    pop         = raise_type_error
    popitem     = raise_type_error



@util.call()
class NoDefaultValue(object):
    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __repr__(self):
        return "NoDefaultValue"


def _extract_arguments(function):
    """
    Extracts arguments from a function, returns a list of tuples
    in the format of (argument, default) where default can be
    `NoDefaultValue` indicating there was no default value.

    This function currently ignores *args and **kwargs type
    arguments.
    """
    argspec = inspect.getargspec(function)

    options = []

    defaults = argspec.defaults or []
    args     = argspec.args     or []

    if defaults:
        # First we put in the arguments we know have no default value
        other_args = args[:- len(defaults)]

        for name in other_args:
            options.append((name, NoDefaultValue))

        # We need to align the rest of args with default values
        args_with_defaults = args[- len(defaults):]

        for name, default in zip(args_with_defaults, argspec.defaults):
            options.append((name, default))
    else:
        options = [(name, NoDefaultValue) for name in args]

    return options