from __future__ import annotations

import sys
from typing import Optional

from .base import StepperDriver, FakeTime
from ..config import SliderConfig


class GPIOUnavailable(Exception):
    pass


class RPiGPIODriver(StepperDriver):
    """RPi.GPIO based driver for STEP/DIR/ENABLE and two endstops.

    Notes:
    - Assumes ENABLE is active-low (DRV8825 style). Adjust if different.
    - Uses BCM numbering.
    """

    def __init__(self, cfg: SliderConfig):
        self.cfg = cfg
        self._GPIO = None  # type: Optional[object]
        self._dir_positive = True

    def setup(self) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore
        except Exception as e:
            raise GPIOUnavailable(str(e))

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        pins = self.cfg.pins
        GPIO.setup(pins.step_pin, GPIO.OUT)
        GPIO.setup(pins.dir_pin, GPIO.OUT)
        GPIO.setup(pins.enable_pin, GPIO.OUT)

        GPIO.setup(pins.min_endstop_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pins.max_endstop_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Default state
        GPIO.output(pins.step_pin, GPIO.LOW)
        GPIO.output(pins.dir_pin, GPIO.LOW)
        # Disable driver by default (active-low enable)
        GPIO.output(pins.enable_pin, GPIO.HIGH)

    def enable(self, enabled: bool) -> None:
        GPIO = self._GPIO
        if not GPIO:
            return
        # Active-low enable
        GPIO.output(self.cfg.pins.enable_pin, GPIO.LOW if enabled else GPIO.HIGH)

    def set_dir(self, positive: bool) -> None:
        GPIO = self._GPIO
        if not GPIO:
            return
        self._dir_positive = positive
        GPIO.output(self.cfg.pins.dir_pin, GPIO.HIGH if positive else GPIO.LOW)

    def pulse_step(self, pulse_us: int) -> None:
        GPIO = self._GPIO
        if not GPIO:
            return
        GPIO.output(self.cfg.pins.step_pin, GPIO.HIGH)
        FakeTime.sleep_us(pulse_us)
        GPIO.output(self.cfg.pins.step_pin, GPIO.LOW)

    def read_min_endstop(self) -> bool:
        GPIO = self._GPIO
        if not GPIO:
            return False
        val = GPIO.input(self.cfg.pins.min_endstop_pin) == GPIO.LOW
        return (not val) if self.cfg.invert_endstops else val

    def read_max_endstop(self) -> bool:
        GPIO = self._GPIO
        if not GPIO:
            return False
        val = GPIO.input(self.cfg.pins.max_endstop_pin) == GPIO.LOW
        return (not val) if self.cfg.invert_endstops else val

    def cleanup(self) -> None:
        if self._GPIO:
            try:
                self._GPIO.cleanup()
            except Exception:
                pass
