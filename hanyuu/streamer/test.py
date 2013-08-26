from collections import namedtuple

Song = namedtuple("Song", ("filename", "metadata"))

def test_dir(directory=u'/media/F/Music', files=None):
    import os
    import mutagen
    files = set() if files is None else files
    for base, dir, filenames in os.walk(directory):
        for name in filenames:
            files.add(os.path.join(base, name))

    def pop_file():
        try:
            filename = files.pop()
        except KeyError:
            return Song(None, None)
        if (filename.endswith('.flac') or
                filename.endswith('.mp3') or
                filename.endswith('.ogg')):
            try:
                meta = mutagen.File(filename, easy=True)
            except:
                meta = u"No metadata available, because I errored."
            else:
                artist = meta.get('artist')
                title = meta.get('title')

                meta = u"{:s} - {:s}" if artist else u"{:s}"

                if artist:
                    artist = u", ".join(artist)
                if title:
                    title = u", ".join(title)
                meta = meta.format(artist, title)
            return Song(filename, meta)
        else:
            return pop_file()
    return pop_file

def test_config(password=None):
    return {'host': 'r-a-d.io',
            'port': 1337,
            'password': password,
            'format': 1,
            'protocol': 0,
            'mount': 'test.mp3'}

class TestQueue(object):
    def __init__(self, func):
        super(TestQueue, self).__init__()
        from collections import deque

        self.queue = deque()
        self.func = func

        for _ in range(20):
            self.queue.append(self.func())

    def peek(self, index=0):
        try:
            return self.queue[index]
        except:
            return None

    def pop(self):
        self.queue.append(self.func())
        return self.queue.popleft()

def tester(password, directory):
    import hanyuu.streamer.manager as m
    from hanyuu.streamer.preloader import PreloadedFileSource
    from hanyuu.streamer.files import FileSource
    from hanyuu.streamer.encoder import Encoder
    from hanyuu.streamer.icecast import Icecast

    hackie = [None]
    source = test_dir(directory)

    poppie = TestQueue(source)
    print poppie.queue
    #def poppie():
    #    filename, metadata = source()
    #    hackie[0].emit("metadata", metadata)
    #    return filename

    config = {"icecast_config": test_config(password)}

    manager = m.Manager(poppie, [PreloadedFileSource, FileSource, Encoder, Icecast], config)
    hackie[0] = manager


    print hackie
    return manager
