from __future__ import absolute_import
from __future__ import unicode_literals

import threading
import logging
from collections import deque, namedtuple

import chan

from .files import AudioFile


logger = logging.getLogger("streamer.preloader")
Options = namedtuple("Options", ("preload_amount",
                                 "preload_full_amount",
                                 "preload_percentage",
                                 "preload_push_percentage"))


class PreloadedFileSource(object):
    options = {
        "preload_amount": 5,
        "preload_full_amount": 2,
        "preload_percentage": 0.5,
        "preload_push_percentage": 0.8,
    }

    def __init__(self, manager, pipe, options):
        super(PreloadedFileSource, self).__init__()

        self.manager = manager
        self.running = threading.Event()

        self.queue = manager.source

        self.preload_count = int(options["preload_amount"])
        self.preload_full_amount = int(options["preload_full_amount"])
        self.preload_percentage = float(options["preload_percentage"])
        self.preload_push_percentage = float(
            options["preload_push_percentage"]
        )

        self.options = Options(
            self.preload_count,
            self.preload_full_amount,
            self.preload_percentage,
            self.preload_push_percentage,
        )

        self.preloaded = deque()

    def book_keeper(self, init):
        new_song = self.manager.register("preload_new_song")
        preload_next = self.manager.register("preload_next")
        push = self.manager.register("preload_push")
        self.exit = exit = self.manager.register("preload_exit")
        start = self.manager.register("metadata")

        # We are done setting up, so push the init and close it.
        init.put(True)
        init.close()

        channels = [new_song, preload_next, push, exit, start]

        # State variables
        first_song = True
        last_preload_index = 0
        while True:
            action, value = chan.chanselect(channels, [])

            audiofile = None

            # This is entered whenever a new song needs to be added from
            # the queue.
            if action is new_song:
                # Find the index in the queue we want
                index = len(self.preloaded)
                song = self.queue.peek(index=index)

                # Make sure we didn't reach the end of the queue.
                if song is None:
                    logger.debug("Empty source queue found.")
                    continue

                logger.debug("Adding new track: %s", song.metadata)

                audiofile = PreloadedAudioFile(song,
                                               self.manager,
                                               self.options)

                self.preloaded.append(audiofile)

                if len(self.preloaded) <= self.preload_full_amount:
                    self.manager.emit("preload_next", True)

                # If this is the first song, we need to push it so that
                # there is something ready right away.
                if first_song:
                    self.manager.emit("preload_push", True)
                    first_song = False

            elif action is preload_next:
                try:
                    audiofile = self.preloaded[last_preload_index]
                except IndexError:
                    # No more songs? just do nothing.
                    logging.debug("Empty queue, failed to start preload.")
                    continue

                logger.debug("Starting preload on: %s", audiofile.metadata)
                start_thread(audiofile.preload)

                last_preload_index += 1

            elif action is push:
                # Get the left most item, the next one to play
                audiofile = self.preloaded[0]

                # Make sure the song has been preloaded fully
                if not audiofile.finished.is_set():
                    # The file hasn't been fully loaded, ditch it
                    # for one that doesn't preload at all.
                    logger.debug("Song hasn't preloaded yet, giving out non-preload.")
                    audiofile = audiofile.non_preload()

                logger.debug("Pushing audiofile: %s", audiofile.metadata)
                # And push it away!
                self.manager.emit("audiofile", audiofile)
                # Don't forget to add a new song to replace the old one.
                self.manager.emit("preload_new_song", True)

            elif action is start:
                # Pop the song from the actual queue first
                song = self.queue.pop()
                # Then pop it from our internal one.
                self.preloaded.popleft()

                # Make sure to update our index of preloadness
                last_preload_index -= 1
                # And limit it to 0 so we don't go negative
                last_preload_index = (last_preload_index if
                                      last_preload_index > 0 else 0)

                logger.debug("Starting audiofile: %s", song.metadata)

            elif action is exit:
                # We are wanted to exit, lets do so
                # First cleanup our files
                for audiofile in self.preloaded:
                    audiofile.close()
                # Then break out.
                break

            # Delete our references.
            del audiofile

        for c in channels:
            c.close()

    def start(self):
        # Check if we aren't already running
        if self.running.is_set():
            return

        # Now start our book keeper
        init = chan.Chan()
        self.keeper_thread = start_thread(self.book_keeper, init)
        init.get()

        # Fill up with audio files to preload
        for _ in range(self.preload_count):
            self.manager.emit("preload_new_song", True)

        self.running.set()

    def close(self):
        for audiofile in self.preloaded:
            audiofile.close()

        self.manager.emit("preload_exit", True)

        self.running.clear()


def progress_function(self, current, total):
    percentage = 1.0 / total * current
    if (percentage >= self.options.preload_percentage and
            not self.preloaded_next):
        # We should preload the next song
        self.manager.emit("preload_next", True)
        self.preloaded_next = True
    if (percentage >= self.options.preload_push_percentage and
            not self.preloaded_push):
        # We have to push a new song to the encoder
        self.manager.emit("preload_push", True)
        self.preloaded_push = True


class PreloadedAudioFile(AudioFile):
    def __init__(self, song, manager, options):
        super(PreloadedAudioFile, self).__init__(song.filename)
        self.song = song
        self.manager = manager
        self.options = options

        self._metadata = None
        self.buffer = None

        self.current_index = 0
        self.total_index = 0

        self.preloaded_next = self.preloaded_push = False
        self.first = True

        self.finished = threading.Event()

    @property
    def metadata(self):
        return self._metadata or self.song.metadata

    def preload(self):
        # This is a database access (at least, most likely)
        self._metadata = self.song.metadata

        frame_buffer = []

        while True:
            data = self._reader.read(self.total_frames)
            if not data:
                break
            frame_buffer.append(data.to_bytes(False, True))

        self.buffer = b''.join(frame_buffer)
        self.total_index = len(self.buffer)

        self.finished.set()

    def non_preload(self):
        return NormalAudioFile(self.song, self.manager, self.options)

    upper_progress = progress_function

    def read(self, size=4096, timeout=10.0):
        # If it's the first time we are being read from, we will want to
        # send a metadata event.
        if self.first:
            self.manager.emit("metadata", self.metadata)
        self.first = False

        if self.buffer is None:
            # If for some reason someone is reading from here, without us
            # actually being preloaded, we will want to just return EOF
            self.upper_progress(100, 100)
            return b''

        # Make sure we aren't going to end up on an edge
        size = size * 2

        start = self.current_index
        self.current_index += size
        self.upper_progress(self.current_index, self.total_index)
        return self.buffer[start:start + size]


class NormalAudioFile(AudioFile):
    def __init__(self, song, manager, options):
        super(NormalAudioFile, self).__init__(song.filename)
        self.metadata = song.metadata
        self.manager = manager
        self.options = options
        self.first = True

        self.preloaded_next = self.preloaded_push = False

    progress = progress_function

    def read(self, size=4096, timeout=0.0):
        if self.first:
            self.manager.emit("metadata", self.metadata)
        self.first = False

        return super(NormalAudioFile, self).read(size, timeout)


def start_thread(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread
