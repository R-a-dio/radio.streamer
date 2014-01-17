from __future__ import absolute_import
import time

import pytest

from . import garbage


def test_collector_singleton():
    assert garbage.Collector() is garbage.Collector()


def test_garbage_collection(working_garbage):
    working = working_garbage(True)

    time.sleep(2)

    assert not working.item


def test_garbage_collection_failure(broken_garbage, working_garbage):
    """
    Test that a raised exception in a garbages `collect`
    method does not cause any side effects for others
    """
    # They don't normally share collector, so we set them to the same
    # one before doing anything.
    broken_garbage.collector = working_garbage.collector

    broken  = broken_garbage(True)
    working = working_garbage(True)

    time.sleep(2)

    assert broken.item
    assert not working.item


@pytest.fixture
def broken_garbage():
    class BrokenTestGarbage(garbage.Garbage):
        collector = garbage.Collector._create_new_collector(timeout=1)
        def collect(self):
            raise ValueError("Collection not possible.")

    return BrokenTestGarbage


@pytest.fixture
def working_garbage():
    class TestGarbage(garbage.Garbage):
        collector = garbage.Collector._create_new_collector(timeout=1)
        def collect(self):
            self.item = False
            return True

    return TestGarbage