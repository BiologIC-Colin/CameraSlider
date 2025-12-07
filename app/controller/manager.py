from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any, Tuple, List

from ..config import load_config, SliderConfig
from ..hardware.base import StepperDriver
from ..hardware.gpio_driver import RPiGPIODriver, GPIOUnavailable
from ..hardware.sim_driver import SimulatorDriver
from ..motion.models import MotionProfile
from ..motion.planner import sample_profile

log = logging.getLogger(__name__)


CommandType = Literal["home", "jog", "run_profile", "prime"]


@dataclass
class Command:
    type: CommandType
    args: Dict[str, Any]


class SliderController:
    def __init__(self):
        self.cfg: SliderConfig = load_config()
        self.driver: StepperDriver = self._init_driver()
        self.driver.enable(False)

        self.steps_per_mm: float = self.cfg.steps_per_mm
        self.current_pos_mm: float = 0.0
        self.homed: bool = False
        self.status: str = "idle"
        self.error: Optional[str] = None
        self.progress: float = 0.0

        self._cmd_q: "queue.Queue[Command]" = queue.Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        # Presets storage
        self._data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self._data_dir, exist_ok=True)
        self._presets_file = os.path.join(self._data_dir, "presets.json")
        if not os.path.exists(self._presets_file):
            with open(self._presets_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _init_driver(self) -> StepperDriver:
        try:
            drv = RPiGPIODriver(self.cfg)
            drv.setup()
            log.info("Using RPi.GPIO driver")
            return drv
        except Exception as e:
            log.info(f"Falling back to Simulator driver: {e}")
            sim = SimulatorDriver(self.cfg)
            sim.setup()
            return sim

    # Public API
    def enqueue_home(self) -> None:
        self._cmd_q.put(Command("home", {}))

    def enqueue_jog(self, distance_mm: float, speed_mm_s: float) -> None:
        self._cmd_q.put(Command("jog", {"distance_mm": distance_mm, "speed_mm_s": speed_mm_s}))

    def enqueue_run_profile(self, profile: MotionProfile) -> None:
        self._cmd_q.put(Command("run_profile", {"profile": profile}))

    def enqueue_prime(self, profile: MotionProfile) -> None:
        self._cmd_q.put(Command("prime", {"profile": profile}))

    def stop(self) -> None:
        self._stop_event.set()
        # Clear pending commands
        while not self._cmd_q.empty():
            try:
                self._cmd_q.get_nowait()
            except queue.Empty:
                break

    def get_status(self) -> dict:
        return {
            "status": self.status,
            "pos_mm": round(self.current_pos_mm, 3),
            "homed": self.homed,
            "progress": round(self.progress, 3),
            "error": self.error,
        }

    # Presets
    def list_presets(self) -> Dict[str, dict]:
        try:
            with open(self._presets_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_preset(self, name: str, profile: MotionProfile) -> None:
        data = self.list_presets()
        data[name] = json.loads(profile.model_dump_json())
        with open(self._presets_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def delete_preset(self, name: str) -> None:
        data = self.list_presets()
        if name in data:
            data.pop(name)
            with open(self._presets_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    # Worker and motion primitives
    def _worker_loop(self) -> None:
        while True:
            cmd = self._cmd_q.get()
            self._stop_event.clear()
            self.error = None
            try:
                if cmd.type == "home":
                    self._do_home()
                elif cmd.type == "jog":
                    self._do_jog(cmd.args["distance_mm"], cmd.args["speed_mm_s"])
                elif cmd.type == "run_profile":
                    self._do_run_profile(cmd.args["profile"])
                elif cmd.type == "prime":
                    self._do_prime(cmd.args["profile"])
            except Exception as e:
                log.exception("Command failed")
                self.error = str(e)
                self.status = "error"
                self.driver.enable(False)

    def _do_home(self) -> None:
        self.status = "homing"
        self.driver.enable(True)
        # Move toward min endstop until pressed
        log.info("Homing: seeking min endstop")
        self._seek_endstop(min_endstop=True, speed_mm_s=self.cfg.max_speed_mm_s * 0.25, max_travel_mm=self.cfg.travel_mm + 10)
        if self._stop_event.is_set():
            self.driver.enable(False)
            self.status = "idle"
            return
        # Back off 5mm
        self._relative_move(5.0, speed_mm_s=30.0)
        # Approach slowly
        self._seek_endstop(min_endstop=True, speed_mm_s=15.0, max_travel_mm=10.0)
        self.current_pos_mm = 0.0
        self.homed = True
        self.driver.enable(False)
        self.status = "idle"
        log.info("Homing complete, pos=0")

    def _do_jog(self, distance_mm: float, speed_mm_s: float) -> None:
        self.status = "jogging"
        self.driver.enable(True)
        spd = max(1.0, min(speed_mm_s, self.cfg.max_speed_mm_s))
        self._relative_move(distance_mm, spd)
        self.driver.enable(False)
        self.status = "idle"

    def _do_prime(self, profile: MotionProfile) -> None:
        """Move directly to the starting position of the given profile.

        If not homed, perform an automatic home first. Uses a conservative
        priming speed for safety. Skips movement if already at start within tolerance.
        """
        self.status = "priming"
        # Auto-home if not homed
        if not self.homed:
            self._do_home()
            if self._stop_event.is_set():
                self.status = "stopped"
                return
        # Determine start position
        try:
            start_pos = float(profile.keyframes[0].pos_mm)
        except Exception:
            start_pos = 0.0
        start_pos = max(0.0, min(start_pos, self.cfg.travel_mm))

        # If already at start within tolerance, nothing to do
        if abs(self.current_pos_mm - start_pos) <= 0.5:
            self.status = "idle"
            return

        # Move to start at a safe speed
        prime_speed = min(50.0, self.cfg.max_speed_mm_s)
        self.driver.enable(True)
        try:
            self._move_to_position(start_pos, max_speed_mm_s=prime_speed)
        finally:
            self.driver.enable(False)
        self.status = "idle"

    def _do_run_profile(self, profile: MotionProfile) -> None:
        self.status = "running"
        self.driver.enable(True)
        times, pos = sample_profile(profile, dt=0.02)
        total_t = max(1e-6, times[-1])

        # Iterate over consecutive samples and execute steps uniformly over each interval
        start_time = time.perf_counter()
        for i in range(len(times) - 1):
            if self._stop_event.is_set():
                break
            t0, t1 = times[i], times[i + 1]
            p0, p1 = pos[i], pos[i + 1]
            dt = max(1e-4, t1 - t0)
            dp_mm = max(0.0, min(p1, self.cfg.travel_mm)) - max(0.0, min(p0, self.cfg.travel_mm))

            steps = int(round(abs(dp_mm) * self.steps_per_mm))
            # Real-time deadline for this segment relative to profile start
            seg_deadline = start_time + t1

            direction_positive = dp_mm > 0
            self.driver.set_dir(direction_positive)

            period_s = dt / steps if steps > 0 else dt
            # Enforce minimal pulse constraints
            min_period_s = max((self.cfg.step_pulse_us * 2) / 1_000_000.0, 1.0 / 20000.0)
            period_s = max(period_s, min_period_s)
            # Also clamp by max allowed speed
            max_steps_per_s = self.cfg.max_speed_mm_s * self.steps_per_mm
            period_s = max(period_s, 1.0 / max_steps_per_s)
            pulse_us = self.cfg.step_pulse_us

            stepped = 0
            # Step until we hit either the step count or the time deadline
            while stepped < steps:
                if self._stop_event.is_set():
                    break
                # Endstop checks
                if direction_positive and self.driver.read_max_endstop():
                    log.warning("Max endstop hit during profile; stopping segment")
                    break
                if (not direction_positive) and self.driver.read_min_endstop():
                    log.warning("Min endstop hit during profile; stopping segment")
                    break
                # If we are at/over the deadline, stop this segment to avoid overrunning profile time
                if time.perf_counter() >= seg_deadline:
                    break
                self.driver.pulse_step(pulse_us)
                self.current_pos_mm += (1 if direction_positive else -1) / self.steps_per_mm
                # Clamp
                self.current_pos_mm = max(0.0, min(self.current_pos_mm, self.cfg.travel_mm))
                stepped += 1
                # Sleep, but do not exceed the segment deadline
                now = time.perf_counter()
                if now < seg_deadline:
                    # Remaining time until deadline
                    remaining = seg_deadline - now
                    time.sleep(min(period_s, remaining))

            # If we finished early (e.g., steps were 0 or clamped), wait out the remainder of the segment time
            now = time.perf_counter()
            if now < seg_deadline and not self._stop_event.is_set():
                time.sleep(seg_deadline - now)
            self.progress = (t1 / total_t)

        # Ensure we stop exactly at the end of the profile timeline
        # Snap to the final planned position to avoid a slow tail due to residual timing
        try:
            self.current_pos_mm = max(0.0, min(pos[-1], self.cfg.travel_mm))
        except Exception:
            pass

        self.driver.enable(False)
        self.status = "idle" if not self._stop_event.is_set() else "stopped"
        self.progress = 1.0 if self.status == "idle" else self.progress

    # Low-level movement helpers
    def _move_to_position(self, target_pos_mm: float, max_speed_mm_s: float) -> None:
        delta_mm = target_pos_mm - self.current_pos_mm
        if abs(delta_mm) < 0.001:
            return
        self._relative_move(delta_mm, speed_mm_s=max_speed_mm_s)

    def _relative_move(self, distance_mm: float, speed_mm_s: float) -> None:
        # limit to travel
        target = max(0.0, min(self.current_pos_mm + distance_mm, self.cfg.travel_mm))
        distance_mm = target - self.current_pos_mm
        if abs(distance_mm) < 1e-6:
            return
        steps_total = int(round(abs(distance_mm) * self.steps_per_mm))
        direction_positive = distance_mm > 0
        self.driver.set_dir(direction_positive)

        # Step period based on speed
        speed_mm_s = max(1.0, min(speed_mm_s, self.cfg.max_speed_mm_s))
        steps_per_s = speed_mm_s * self.steps_per_mm
        # Ensure minimal low/high time per pulse
        min_period_s = max((self.cfg.step_pulse_us * 2) / 1_000_000.0, 1.0 / 20000.0)  # cap at 20 kHz
        period_s = max(1.0 / steps_per_s, min_period_s)
        pulse_us = self.cfg.step_pulse_us

        for i in range(steps_total):
            if self._stop_event.is_set():
                break
            # Endstop checks
            if direction_positive and self.driver.read_max_endstop():
                log.warning("Max endstop hit during move; stopping")
                break
            if (not direction_positive) and self.driver.read_min_endstop():
                log.warning("Min endstop hit during move; stopping")
                break

            self.driver.pulse_step(pulse_us)
            self.current_pos_mm += (1 if direction_positive else -1) / self.steps_per_mm
            time.sleep(period_s)

    def _seek_endstop(self, min_endstop: bool, speed_mm_s: float, max_travel_mm: float) -> None:
        # Choose direction
        direction_positive = not min_endstop
        self.driver.set_dir(direction_positive)

        steps_limit = int(round(abs(max_travel_mm) * self.steps_per_mm))
        steps_per_s = max(1.0, speed_mm_s * self.steps_per_mm)
        min_period_s = max((self.cfg.step_pulse_us * 2) / 1_000_000.0, 1.0 / 20000.0)
        period_s = max(1.0 / steps_per_s, min_period_s)
        pulse_us = self.cfg.step_pulse_us

        for i in range(steps_limit):
            if self._stop_event.is_set():
                break
            if min_endstop and self.driver.read_min_endstop():
                break
            if (not min_endstop) and self.driver.read_max_endstop():
                break
            self.driver.pulse_step(pulse_us)
            self.current_pos_mm += (1 if direction_positive else -1) / self.steps_per_mm
            # Clamp
            self.current_pos_mm = max(0.0, min(self.current_pos_mm, self.cfg.travel_mm))
            time.sleep(period_s)


# Singleton getter
_singleton: Optional[SliderController] = None


def get_controller() -> SliderController:
    global _singleton
    if _singleton is None:
        _singleton = SliderController()
    return _singleton
