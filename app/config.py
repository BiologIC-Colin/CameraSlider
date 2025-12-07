from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class GPIOPins:
    step_pin: int = 18  # BCM numbering
    dir_pin: int = 23
    enable_pin: int = 24
    min_endstop_pin: int = 17
    max_endstop_pin: int = 27


@dataclass
class SliderConfig:
    # Mechanics
    steps_per_rev: int = 200           # 1.8° motor
    microstep: int = 16                # DRV8825 typical
    lead_mm_per_rev: float = 8.0       # e.g., TR8x8 lead screw
    travel_mm: float = 1200.0          # 120 cm

    # Motion limits (conservative defaults)
    max_speed_mm_s: float = 120.0
    max_accel_mm_s2: float = 300.0

    # GPIO pins
    pins: GPIOPins = field(default_factory=GPIOPins)

    # Timing
    step_pulse_us: int = 4             # DRV8825 min > 1.9us; use 4us

    # Misc
    invert_endstops: bool = False      # set True if logic inverted

    @property
    def steps_per_mm(self) -> float:
        return (self.steps_per_rev * self.microstep) / self.lead_mm_per_rev


def load_config() -> SliderConfig:
    # In MVP, return defaults; could load from env or file later
    cfg = SliderConfig()
    # Allow simple env overrides
    cfg.travel_mm = float(os.getenv("SLIDER_TRAVEL_MM", cfg.travel_mm))
    cfg.max_speed_mm_s = float(os.getenv("SLIDER_MAX_SPEED", cfg.max_speed_mm_s))
    cfg.max_accel_mm_s2 = float(os.getenv("SLIDER_MAX_ACCEL", cfg.max_accel_mm_s2))
    cfg.pins.step_pin = int(os.getenv("SLIDER_STEP_PIN", cfg.pins.step_pin))
    cfg.pins.dir_pin = int(os.getenv("SLIDER_DIR_PIN", cfg.pins.dir_pin))
    cfg.pins.enable_pin = int(os.getenv("SLIDER_ENABLE_PIN", cfg.pins.enable_pin))
    cfg.pins.min_endstop_pin = int(os.getenv("SLIDER_MIN_PIN", cfg.pins.min_endstop_pin))
    cfg.pins.max_endstop_pin = int(os.getenv("SLIDER_MAX_PIN", cfg.pins.max_endstop_pin))
    cfg.invert_endstops = os.getenv("SLIDER_INVERT_ENDSTOPS", "false").lower() in ("1", "true", "yes")
    return cfg
