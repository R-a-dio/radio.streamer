from __future__ import absolute_import
import functools
import threading
import Queue


"""def ignore_exceptions(function):
    @functools.wraps(function)
    def receive_pipe(pipe, *args, **kwargs):
        while True:
            try:
                for _ in function(pipe, *args, **kwargs):
                    yield _
            except:
                continue
    return receive_pipe"""


def buffered(buffersize, chunksize):
    """
    Buffers the output of the decorated generator.

    This is done with a new thread that executes the generator.

    :param buffersize: The maximum amount of chunks in the queue used between threads
    :param chunksize: The size of chunks used to move between threads

    To get the total amount of 'yields' that can be put in the buffer you can multiply
    `buffersize` and `chunksize`. It is suggested to fiddle around with the sizes in
    tests to determine the best size to use.
    """
    def buffered(function, *args, **kwargs):
        @functools.wraps(function)
        def buffered(*args, **kwargs):
            queue = Queue.Queue(maxsize=buffersize)

            # Create ourself a sentinal to use as StopIteration indicator.
            exit = object()

            def threaded_generator(function, *args, **kwargs):
                # Preallocating is slightly faster than resizing
                chunk = [exit] * chunksize
                index = 0

                for x in function(*args, **kwargs):
                    chunk[index] = x

                    index += 1

                    if index >= chunksize:
                        queue.put(chunk[:])
                        index = 0

                queue.put(chunk[:index])
                queue.put(exit)

            run(threaded_generator, function, *args, **kwargs)

            cont = True
            while True:
                chunk = queue.get()

                # The method to detect the sentinal below is faster
                # than putting an 'if' statement in the for loop
                # below.
                if chunk is exit:
                    break

                for x in chunk:
                    yield x

        return buffered
    return buffered


def run(function, *args, **kwargs):
    thread = threading.Thread(target=function, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()


def call(*args, **kwargs):
    """
    Calls the decorated function or class with the arguments given and
    returns the result.
    """
    def call(func):
        return func(*args, **kwargs)
    return call


class Err(object):
    def __init__(self, name):
        super(Err, self).__init__()
        self.name = name

    def __repr__(self):
        return self.name