from __future__ import unicode_literals
from __future__ import absolute_import
import threading
import datetime
import logging
import time
import abc

from . import util


logger = logging.getLogger(__name__)


class Singleton(type):
    def __init__(mcs, name, bases, dict):
        super(Singleton, mcs).__init__(name, bases, dict)
        mcs.instance = None

    def __call__(mcs, *args, **kw):
        if mcs.instance is None:
            mcs.instance = super(Singleton, mcs).__call__(*args, **kw)
        return mcs.instance


class Collector(object):
    __metaclass__ = Singleton

    def __init__(self, timeout=15):
        super(Collector, self).__init__()
        self.timeout = timeout

        self.items = set()

        self.lock = threading.RLock()
        self.collecting = threading.Event()

        util.run(self.collection_method)

    def add(self, garbage):
        with self.lock:
            self.items.add(garbage)

    def collection_method(self):
        while not self.collecting.is_set():
            collected_items = set()
            with self.lock:
                items = self.items.copy()

            for item in items:
                try:
                    success = item.collect()
                except:
                    logger.exception("Collection Failure.")
                else:
                    if success:
                        collected_items.add(item)

            with self.lock:
                self.items -= collected_items
            time.sleep(self.timeout)

    @classmethod
    def _create_new_collector(cls, timeout=15):
        """
        Internal debugging method to create a new collector.
        """
        ins = cls.instance
        cls.instance = None
        new = cls(timeout)
        cls.instance = ins
        return new



class Garbage(object):
    __metaclass__ = abc.ABCMeta
    collector = Collector()

    def __init__(self, item=None):
        super(Garbage, self).__init__()
        self.item = item

        self.creation_time = datetime.datetime.now()
        self.collector.add(self)

    @abc.abstractmethod
    def collect(self):
        """
        Gets called on each collection cycle.

        Should return a bool indicating if the garbage collection
        was successfull or not.
        """