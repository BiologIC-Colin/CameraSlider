from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Ease(BaseModel):
    type: Literal["linear", "cubic-bezier"] = "linear"
    p: Optional[list[float]] = Field(default=None, description="Bezier control points [x1,y1,x2,y2]")

    @model_validator(mode="after")
    def validate_bezier(self):
        if self.type == "cubic-bezier":
            if not self.p or len(self.p) != 4:
                raise ValueError("cubic-bezier requires p=[x1,y1,x2,y2]")
        return self


class Keyframe(BaseModel):
    t: float = Field(..., ge=0.0, description="Time in seconds")
    pos_mm: float = Field(..., description="Position along slider in mm")
    ease: Ease = Field(default_factory=Ease)


class MotionProfile(BaseModel):
    length_mm: float = Field(..., gt=0)
    keyframes: List[Keyframe]
    max_speed_mm_s: float = Field(120.0, gt=0)
    max_accel_mm_s2: float = Field(300.0, gt=0)

    @model_validator(mode="after")
    def validate_keyframes(self):
        if not self.keyframes or len(self.keyframes) < 2:
            raise ValueError("At least two keyframes required")
        # sort and ensure increasing time
        self.keyframes.sort(key=lambda k: k.t)
        last_t = -1.0
        for k in self.keyframes:
            if k.t <= last_t:
                raise ValueError("Keyframe times must be strictly increasing")
            if k.pos_mm < 0 or k.pos_mm > self.length_mm:
                raise ValueError("Keyframe position outside length")
            last_t = k.t
        return self
