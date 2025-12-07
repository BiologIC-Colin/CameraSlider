Camera Slider MVP (Raspberry Pi 4 + Waveshare HRB8825 HAT)

Overview
This MVP lets you control a NEMA17 stepper-driven camera slider from a Raspberry Pi 4 with two hall-effect endstops. It exposes a small web app and HTTP API to:
- Home the carriage using limit switches
- Jog the carriage by a defined distance
- Run motion sequences defined by keyframes and easing curves (linear or cubic-bezier)
- Save and trigger named transitions (suitable for OBS/Loupedeck via HTTP requests)

Architecture
- Python FastAPI server hosts REST API and static web UI
- Hardware Abstraction Layer (HAL) for Step/Dir driver and endstops
  - RPi.GPIO driver (real hardware)
  - Simulator driver (for development on Windows/macOS/Linux without GPIO)
- Motion Planner creates a time-based position curve from keyframes and easing
- Controller runs in a background thread, stepping toward the planned position

Safety notes
- Always test in Simulator mode first (default on non-Pi)
- Start with conservative speeds/accelerations
- Ensure endstops are correctly wired and logic is correct before real moves

Wiring (Typical)
- Waveshare HRB8825 HAT: use its STEP, DIR, ENABLE lines routed to pins. Update pins in app/config.py
- Two hall-effect sensors as limit switches: normally-open to ground; use pull-ups on GPIO inputs
  - min_endstop_pin = carriage at the 0 mm end
  - max_endstop_pin = carriage at the far end (e.g., 1200 mm for 120 cm)

Install on Raspberry Pi 4
1) Python 3.9+ recommended
2) Clone repo and install deps:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3) Optional: For better timing later, install pigpio and enable the daemon. MVP uses RPi.GPIO.
4) Edit app/config.py to match your pins, steps-per-mm, and travel length.
5) Run server:
   ```bash
   uvicorn app.server.api:app --host 0.0.0.0 --port 8000
   ```
6) Open http://<pi-ip>:8000 in your browser.

Develop on PC (Simulator)
- On Windows/macOS/Linux, the HAL falls back to Simulator automatically.
- Start the server:
  ```bash
  uvicorn app.server.api:app --host 127.0.0.1 --port 8000
  ```

OBS/Loupedeck Integration
- Create named transitions via the web UI (Save Preset)
- Trigger via HTTP GET:
  - `http://<host>:8000/api/run_preset/<name>`
- Other useful endpoints:
  - POST /api/home
  - POST /api/jog {"distance_mm": 50, "speed_mm_s": 50}
  - POST /api/run with a JSON profile (see examples below)
  - POST /api/prime with a JSON profile (auto-homes if needed, moves directly to the profile's start position)
  - GET  /api/prime_preset/<name> (auto-homes if needed, primes to the saved preset's start position)
  - POST /api/stop
  - GET /api/status

JSON Motion Profile (MVP)
```json
{
  "length_mm": 1200,
  "keyframes": [
    {"t": 0.0, "pos_mm": 0.0, "ease": {"type": "linear"}},
    {"t": 4.0, "pos_mm": 400.0, "ease": {"type": "cubic-bezier", "p": [0.25, 0.1, 0.25, 1.0]}},
    {"t": 7.0, "pos_mm": 1200.0, "ease": {"type": "linear"}}
  ],
  "max_speed_mm_s": 120,
  "max_accel_mm_s2": 300
}
```

Priming behavior
- Priming moves the carriage directly to the first keyframe's `pos_mm` before a run.
- If the slider is not homed, the system will automatically home first.
- Movement uses a conservative speed (<= 50 mm/s by default).
- If already within ~0.5 mm of the start, the movement is skipped.

Systemd service (optional)
Create `/etc/systemd/system/camera-slider.service`:
```
[Unit]
Description=Camera Slider API
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/CameraSlider
ExecStart=/home/pi/CameraSlider/.venv/bin/uvicorn app.server.api:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable camera-slider
sudo systemctl start camera-slider
```

Notes and Future Work
- For higher step rates, consider migrating the driver to pigpio waveforms or using a co-processor.
- PTZ: add another HAL for serial/HTTP control of OBSBOT and sync with the motion timeline.
