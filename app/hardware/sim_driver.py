from __future__ import annotations

import logging
from .base import StepperDriver, FakeTime
from ..config import SliderConfig

log = logging.getLogger(__name__)


class SimulatorDriver(StepperDriver):
    """Simulator that logs actions; no real GPIO."""

    def __init__(self, cfg: SliderConfig):
        self.cfg = cfg
        self.enabled = False
        self.dir_positive = True
        self.min_pressed = False
        self.max_pressed = False

    def setup(self) -> None:
        log.info("SimulatorDriver setup complete")

    def enable(self, enabled: bool) -> None:
        self.enabled = enabled
        log.info(f"Driver {'ENABLED' if enabled else 'DISABLED'} (sim)")

    def set_dir(self, positive: bool) -> None:
        self.dir_positive = positive
        log.debug(f"Direction set to {'+' if positive else '-'} (sim)")

    def pulse_step(self, pulse_us: int) -> None:
        if not self.enabled:
            return
        FakeTime.sleep_us(pulse_us)

    def read_min_endstop(self) -> bool:
        return self.min_pressed

    def read_max_endstop(self) -> bool:
        return self.max_pressed

    def cleanup(self) -> None:
        log.info("SimulatorDriver cleanup")
