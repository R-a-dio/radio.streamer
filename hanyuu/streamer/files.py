"""Module that handles file access and decoding to PCM.

It uses python-audiotools for the majority of the work done."""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from . import core
from . import util

import audiotools
import mutagen


@core.input("audiofile")
@core.output("audiofile")
def convert_audio_files(pipe, sample_rate=44100, channels=2,
                        channel_mask=audiotools.ChannelMask(0x1 | 0x2),
                        bits_per_sample=24):
    for audiofile in pipe:
        total_frames = audiofile.total_frames()

        audiofile = audiofile.to_pcm()

        # Convert the PCM to the users needs
        audiofile = audiotools.PCMConverter(
            audiofile,
            sample_rate=sample_rate,
            channels=channels,
            channel_mask=channel_mask,
            bits_per_sample=bits_per_sample,
        )

        yield audiofile


@core.input("filenames")
@core.output("audiofile")
def open_audio_files(pipe):
    """
    Opens given filename with audiotools.
    """
    for filename in pipe:
        if isinstance(filename, unicode):
            filename = filename.encode("utf8")

        try:
            yield audiotools.open(filename)
        except audiotools.UnsupportedFile:
            continue


@core.input("filenames")
@core.output("filenames")
@core.state
def read_audio_metadata(pipe):
    for state, filename in pipe:
        state = state.mutate(filename=filename)

        try:
            metadata = mutagen.File(filename, easy=True)
        except:
            yield state, filename
            continue

        if not metadata:
            yield state, filename
            continue

        metadata = {key: ", ".join(values) for key, values in metadata.iteritems()}

        state = state.mutate(metadata=metadata)

        yield state, filename



@core.input("audiofile")
@core.output("audio_pcm_data")
def read_audio_files(pipe, read_size=4096):
    for audiofile in pipe:
        while True:
            try:
                data = audiofile.read(read_size).to_bytes(False, True)
            except (ValueError) as err:
                # A ValueError means a localized frame error, we return an empty
                # byte string, and hope the next frame is correct.
                continue
            except (AttributeError, IOError) as err:
                # If either of the two exceptions happen it's an unrecoverable
                # error and we will want to stop with the current file.
                break
            else:
                if not data:
                    break
                yield data