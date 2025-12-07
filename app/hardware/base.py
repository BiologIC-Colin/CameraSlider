from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Protocol


class EndstopState(Protocol):
    min_pressed: bool
    max_pressed: bool


class StepperDriver(ABC):
    """Abstract Step/Dir driver with two endstops."""

    @abstractmethod
    def setup(self) -> None:
        ...

    @abstractmethod
    def enable(self, enabled: bool) -> None:
        ...

    @abstractmethod
    def set_dir(self, positive: bool) -> None:
        ...

    @abstractmethod
    def pulse_step(self, pulse_us: int) -> None:
        """Emit one step pulse with given high time in microseconds."""
        ...

    @abstractmethod
    def read_min_endstop(self) -> bool:
        ...

    @abstractmethod
    def read_max_endstop(self) -> bool:
        ...

    @abstractmethod
    def cleanup(self) -> None:
        ...


class FakeTime:
    """Small helper to sleep for microseconds in a portable way."""

    @staticmethod
    def sleep_us(us: int) -> None:
        # time.sleep has limited resolution; this is MVP-grade
        time.sleep(max(us, 0) / 1_000_000.0)
