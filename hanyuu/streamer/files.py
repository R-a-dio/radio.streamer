"""Module that handles file access and decoding to PCM.

It uses python-audiotools for the majority of the work done."""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

import threading
import logging

from . import garbage
import audiotools


logger = logging.getLogger("streamer.files")


class AudioError(Exception):
    """Exception raised when an error occurs in this module."""
    pass


class GarbageAudioFile(garbage.Garbage):
    """Garbage class of the AudioFile class"""
    def collect(self):
        """Tries to close the AudioFile resources when called."""
        try:
            self.item._reader.close()
        except (audiotools.DecodingError):
            pass
        # Hack to kill zombies below
        import gc
        import subprocess

        try:
            [item.poll() for item in gc.get_referrers(subprocess.Popen)
             if isinstance(item, subprocess.Popen)]
        except:
            logger.warning("Exception occured in hack.")
        # Hack to kill zombies above

        del self.item._reader

        return True


# TODO: Add handler hooks.
class FileSource(object):
    def __init__(self, manager, pipe, options):
        super(FileSource, self).__init__()
        self.manager = manager

        self.audiofile = None

        self.pipe = pipe
        # If the pipe is None, it means there are no pipes before us
        # we then assume that `manager.source` is a callable that
        # returns filenames that we should stream.

        # Otherwise, it means a pipe is before us, we assume that this pipe
        # supplies us with AudioFile instances through an event.
        if pipe is None:
            self.processor = self.filename_processor
        else:
            self.processor = self.audiofile_processor
            self.channel = self.manager.register("audiofile")

        self.options = options

        self.eof = threading.Event()

    def audiofile_processor(self):
        return self.channel.get()

    def filename_processor(self):
        filename = self.manager.source()

        if filename is None:
            return

        try:
            audiofile = AudioFile(filename)
        except (AudioError):
            logger.exception("Unsupported file.")
            return self.filename_processor()
        except (IOError):
            logger.exception("Failed opening file.")
            return self.filename_processor()
        else:
            return audiofile

    def processor(self):
        pass

    def read(self, size=4096, timeout=10.0):
        if self.eof.is_set():
            return b''

        # We either don't have a file yet, or just reached the
        # end of a file and need a new one. Go fetch one.
        if self.audiofile is None:
            new = self.processor()
            if new is None:
                self.close()
                return b''
            else:
                self.audiofile = new

        try:
            data = self.audiofile.read(size, timeout)
        except (ValueError) as err:
            # A ValueError means a localized frame error, we return an empty
            # byte string, and hope the next frame is correct.
            return b''
        except (AttributeError, IOError) as err:
            # If either of the two exceptions happen it's an unrecoverable
            # error and we will want to stop with the current file.
            data = b''

        if data == b'':
            self.audiofile.close()
            self.audiofile = None
            return self.read(size, timeout)
        return data

    def start(self):
        self.eof.clear()
        self.audiofile = self.processor()

    def close(self):
        self.eof.set()

    def __getattr__(self, key):
        return getattr(self.audiofile, key)


class AudioFile(object):
    """A Simple wrapper around the audiotools library.

    This opens the filename given wraps the file in a PCMConverter that
    turns it into PCM of format 44.1kHz, Stereo, 24-bit depth."""
    def __init__(self, filename):
        super(AudioFile, self).__init__()
        self._reader = self._open_file(filename)
        self.filename = filename

    def read(self, size=4096, timeout=0.0):
        """Returns at most a string of size `size`.

        The `timeout` argument is unused. But kept in for compatibility with
        other read methods in the `audio` module."""
        return self._reader.read(size).to_bytes(False, True)

    def close(self):
        """Registers self for garbage collection. This method does not
        close anything and only registers itself for colleciton."""
        logger.debug("Closing audiofile: %s", self.filename)
        GarbageAudioFile(self)

    def __getattr__(self, key):
        try:
            return getattr(self._reader, key)
        except (AttributeError):
            return getattr(self.file, key)

    def progress(self, current, total):
        """Dummy progress function"""
        pass

    def _open_file(self, filename):
        """Open a file for reading and wrap it in several helpers."""
        # Audiotools seems to hate unicode, so we.. don't give it that
        if isinstance(filename, unicode):
            filename = filename.encode('utf8')

        try:
            reader = audiotools.open(filename)
        except (audiotools.UnsupportedFile):
            raise AudioError("Unsupported file")

        self.file = reader
        total_frames = reader.total_frames()

        # Wrap in a PCMReader because we want PCM
        reader = reader.to_pcm()

        # Wrap in a converter
        reader = audiotools.PCMConverter(
            reader, sample_rate=44100, channels=2,
            channel_mask=audiotools.ChannelMask(0x1 | 0x2),
            bits_per_sample=24,
        )

        # And for file progress!
        reader = audiotools.PCMReaderProgress(reader, total_frames,
                                              self.progress)

        return reader
