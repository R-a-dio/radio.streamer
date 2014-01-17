"""
A very simple encoder module.

The encoders currently supported are listed below:

    - LAME MP3 encoder

Other formats would require a rework of this module to be more generic.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from . import core
from . import util
from . import garbage
from .util import Err

import subprocess
import logging
import select
import decimal
import os


logger = logging.getLogger(__name__)

NoErr             = None
CleanUp           = Err("CleanUp")
NeedMoreData      = Err("NeedMoreData")
NoMoreData        = Err("NoMoreData")
RetryWithSameData = Err("RetryWithSameData")


@util.call(b'')
class NoData(bytes):
    pass


class LameError(Exception):
    pass


def lame_encoder(initial_data, select_timeout=3, read_size=4096, bitrate=192,
                          sample_rate=44100, source_sample_rate=44100,
                          source_bits_per_sample=24):
    """
    Generator that returns a tuple containing (data, err):

    `data` can either be:
        1. `NoData` indicating there was no data to return
        2. `bytes` mp3 audio data

    `err` can be one of these:
        1. NoErr: No error occured, you can continue reading
        2. NeedMoredata: There isn't enough data to encode.
        3. LameError instance indicates there was an unrecoverable error
        4. RetryWithSameData: Indicates we could not write the data off and to
                              prevent data loss, you will need to resend it.

    It also accepts one of two things:

        1. `bytes`: PCM audio data to encode to mp3
        2. NoMoreData: Indicate to clean up resources and exit the generator.

    parameters:
        General:
        - initial_data          : An initial `bytes` object to write.
        - select_timeout        : The timeout in seconds to pass to `select.select`
        - read_size             : The amount of bytes to read from `process.stdout`

        MP3/Lame related:
        - bitrate               : The resulting mp3's bitrate, CBR.
        - sample_rate           : Sample rate of the resulting mp3
        - source_sample_rate    : Sample rate of the PCM data
        - bits_per_sample       : Amount of bits per sample in the PCM data
    """
    logger.debug("Starting new lame encoder instance: %s", repr(locals()))
    arguments = [
        'lame', '--quiet',
        '--flush',
        '-r',
        '-s', str(decimal.Decimal(source_sample_rate) / 1000),
        '--bitwidth', str(source_bits_per_sample),
        '--signed', '--little-endian',
        '-m', 'j',
        '--cbr', '-b', str(bitrate),
        '--resample',  str(decimal.Decimal(sample_rate) / 1000),
        '-', '-',
    ]

    lame_stdin, stdin = create_pipes()
    stdout, lame_stdout = create_pipes()

    try:
        process = subprocess.Popen(
            args=arguments,
            stdin=lame_stdin,
            stdout=lame_stdout,
        )
    except OSError as err:
        if err.errno == 2:
            print("You don't have LAME installed.")

        raise
    else:
        process.files = [
            lame_stdin,
            lame_stdout,
            stdin,
            stdout,
        ]

    data = initial_data
    while True:
        return_value, err_value = NoData, NoErr

        reader, writer, error = select.select(
            [stdout],
            [stdin],
            [stdout, stdin],
            select_timeout,
        )

        if not reader and not writer and not error:
            logger.debug("Nothing is ready")
            err_value = NeedMoreData

        if error:
            logger.debug(error)

        if reader:
            return_value = os.read(reader[0].fileno(), read_size)
        else:
            # There is nothing to read yet, so just keep
            # asking for more data.
            err_value = NeedMoreData

        # Handle possible writes or lack of such
        if writer:
            try:
                writer[0].write(data)
            except (IOError, ValueError) as err:
                logger.exception("LAME error occured")
                err_value = LameError(str(err))
            except:
                logger.exception("LAME unknown error occured")
                err_value = LameError(str(err))
        else:
            # We could not write due to the buffer being full,
            # request that we get the same data as last time to
            # try again.
            err_value = RetryWithSameData

        if isinstance(err_value, LameError):
            # A LameError is unrecoverable in here, so we can clean
            # ourself before returning.
            SubprocessGarbage(process)

        data = yield return_value, err_value

        if data is NoMoreData or data is CleanUp:
            SubprocessGarbage(process)
            break


@core.input("audio_pcm_data")
@core.output("audio_mp3_data")
@core.config(name="lame", redirect=lame_encoder, only_with_defaults=True)
def encode_pcm_with_lame(pipe, **config):
    """
    Encodes PCM audio data to MP3.

    For possible `config` keys see `lame_encoder`.
    """
    while True:
        encoder = lame_encoder(b'', **config)
        # Start the encoder
        encoder.send(None)

        for data in pipe:
            while True:
                mp3_data, err = encoder.send(data)

                if err is RetryWithSameData:
                    yield mp3_data
                else:
                    break

            if err is NeedMoreData:
                # Encoder needs more data to encode before we
                # can read anything.
                continue
            elif isinstance(err, LameError):
                # Something went wrong, we should go looking for a new
                # encoder to use.
                if mp3_data:
                    yield mp3_data
                break

            # We just got normal data, send it away
            yield mp3_data
        else:
            # We ran dry our input pipe, make sure there is nothing left to read
            # from the encoder, and then exit nicely
            mp3_data, err = NoData, NoErr
            while err == NoErr:
                mp3_data, err = encoder.send(NoMoreData)

                if mp3_data:
                    yield mp3_data

            break

        # Send a cleanup message
        encoder.send(CleanUp)

    # Send a cleanup message since we break abruptly above.
    encoder.send(CleanUp)


class SubprocessGarbage(garbage.Garbage):
    """
    Garbage collection object for lame subprocesses.
    """
    def collect(self):
        self.counter = getattr(self, 'counter', 0)

        # Close all the fd's used for communicating
        for f in self.item.files:
            f.close()

        # Check if our encoder process is down yet
        returncode = self.item.poll()

        # If we're still around after 2 calls, just call kill and hope
        # for the best.
        #if self.counter >= 2:
        #    self.item.kill()

        self.counter += 1

        if returncode is None:
            return False
        return True


def create_pipes():
    i, o = os.pipe()
    return os.fdopen(i, 'r'), os.fdopen(o, 'w')