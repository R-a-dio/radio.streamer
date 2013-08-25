from __future__ import absolute_import
from collections import defaultdict
import threading

import chan


class Manager(object):
    def __init__(self, source, pipes, options=None):
        super(Manager, self).__init__()
        self.events = defaultdict(list)

        options = options or {}

        # Keep the options directory around for later?
        self.options = options
        # The source is always on the manager, and isn't passed to any pipes
        self.source = source

        # Bookkeeping on start/close calls!
        self.started = threading.Event()

        self.pipe_instances = []

        previous_pipe = None
        for pipe in pipes:
            # Get the default options for this pipe, if any.
            pipe_options = getattr(pipe, "options", {})
            # Update them with the passed options we have.
            pipe_options.update(options)

            instance = pipe(self, previous_pipe, pipe_options)

            self.pipe_instances.append(instance)

            previous_pipe = instance

    def start(self):
        """
        Starts the manager and pipes registered.

        .. warning::
            Exceptions are propagated.
        """
        if not self.started.is_set():
            for instance in self.pipe_instances:
                instance.start()
            self.started.set()

    def close(self):
        """
        Closes the manager and pipes registered.

        .. warning::
            Exceptions are propagated.
        """
        self.started.clear()

        for instance in self.pipe_instances:
            instance.close()

    def register(self, event):
        """
        Register yourself for an event, you will receive a channel that
        receives any events that are triggered for the event.

        :parameter event: The event to register for.
        :returns: :class:`chan.Chan`
        """
        c = chan.Chan(buflen=5)

        self.events[event].append(c)

        return c

    def emit(self, event, obj):
        """
        Emits an event to all channels registered.

        :parameter event: The event to emit for.
        :parameter obj: The object to send on the channel with the emit.
        """
        channels = self.events.get(event, [])
        for c in channels:
            try:
                c.put(obj)
            except chan.ChanClosed:
                channels.remove(c)
                continue
        self.events[event] = channels
