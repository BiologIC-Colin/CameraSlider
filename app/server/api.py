from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..controller.manager import get_controller
from ..motion.models import MotionProfile

log = logging.getLogger(__name__)


app = FastAPI(title="Camera Slider API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JogRequest(BaseModel):
    distance_mm: float = Field(...)
    speed_mm_s: float = Field(50.0, gt=0)


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def root_page():
    index_file = static_dir / "index.html"
    return FileResponse(str(index_file))


@app.get("/api/status")
def api_status():
    ctl = get_controller()
    return ctl.get_status()


@app.post("/api/home")
def api_home():
    ctl = get_controller()
    ctl.enqueue_home()
    return {"ok": True}


@app.post("/api/jog")
def api_jog(req: JogRequest):
    ctl = get_controller()
    ctl.enqueue_jog(req.distance_mm, req.speed_mm_s)
    return {"ok": True}


@app.post("/api/run")
def api_run(profile: MotionProfile):
    ctl = get_controller()
    ctl.enqueue_run_profile(profile)
    return {"ok": True}


@app.post("/api/prime")
def api_prime(profile: MotionProfile):
    """Move directly to the starting position of the provided profile.

    Behavior:
    - If the slider is not homed, an automatic home is performed first.
    - Movement uses a conservative speed.
    - If already at the start within tolerance, no move is performed.
    """
    ctl = get_controller()
    ctl.enqueue_prime(profile)
    return {"ok": True}


@app.post("/api/stop")
def api_stop():
    ctl = get_controller()
    ctl.stop()
    return {"ok": True}


@app.get("/api/presets")
def api_presets_list():
    ctl = get_controller()
    return ctl.list_presets()


@app.post("/api/presets/{name}")
def api_preset_save(name: str, profile: MotionProfile):
    ctl = get_controller()
    ctl.save_preset(name, profile)
    return {"ok": True}


@app.delete("/api/presets/{name}")
def api_preset_delete(name: str):
    ctl = get_controller()
    ctl.delete_preset(name)
    return {"ok": True}


@app.get("/api/run_preset/{name}")
def api_run_preset(name: str):
    ctl = get_controller()
    data = ctl.list_presets()
    if name not in data:
        raise HTTPException(404, detail="Preset not found")
    prof = MotionProfile(**data[name])
    ctl.enqueue_run_profile(prof)
    return {"ok": True}


@app.get("/api/prime_preset/{name}")
def api_prime_preset(name: str):
    ctl = get_controller()
    data = ctl.list_presets()
    if name not in data:
        raise HTTPException(404, detail="Preset not found")
    prof = MotionProfile(**data[name])
    ctl.enqueue_prime(prof)
    return {"ok": True}
