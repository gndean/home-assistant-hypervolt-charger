from __future__ import annotations
from collections import deque
import time


class TimestampedElement:
    def __init__(self, value):
        self.timestamp = time.time()
        self.value = value

    def age_ms(self):
        return int((time.time() - self.timestamp) * 1000)


class TimestampedQueue:
    """A limited size queue to store elements that are timestamped from when they are added"""

    def __init__(self, max_len=100):
        self.queue = deque(maxlen=max_len)

    def add(self, value):
        timestamped_value = TimestampedElement(value)
        self.queue.append(timestamped_value)

    def head_element(self) -> TimestampedElement | None:
        if len(self.queue) > 0:
            return self.queue[0]

        return None

    def delete_head(self):
        if len(self.queue) > 0:
            self.queue.popleft()

    def delete_old_elements(self, max_age_ms):
        while len(self.queue) > 0 and self.queue[0].age_ms() > max_age_ms:
            self.delete_head()
