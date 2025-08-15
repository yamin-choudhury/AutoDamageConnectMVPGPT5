from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, validator

Severity = Literal["minor", "moderate", "severe"]


class VehicleInfo(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None

    class Config:
        extra = "ignore"


class LLMDetectedPart(BaseModel):
    name: str = Field(..., min_length=1)
    location: Optional[str] = None
    severity: Severity = "minor"

    @validator("severity", pre=True, always=True)
    def _norm_severity(cls, v):  # type: ignore[no-untyped-def]
        if not v:
            return "minor"
        s = str(v).strip().lower()
        if s in ("severe", "high"):  # accept "high" as severe
            return "severe"
        if s in ("moderate", "medium"):
            return "moderate"
        return "minor"

    class Config:
        extra = "forbid"


class DetectionLLMOutput(BaseModel):
    vehicle: VehicleInfo = Field(default_factory=VehicleInfo)
    damaged_parts: List[LLMDetectedPart] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class VerifyLLMOutput(BaseModel):
    present: bool = False
    confidence: float = Field(0.0, ge=0.0, le=1.0)

    class Config:
        extra = "forbid"


# Structures used downstream in reports (not enforced on LLM output directly)
class VerifyPass(BaseModel):
    present: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    temp: Optional[float] = None

    class Config:
        extra = "ignore"


class VerifyEvidence(BaseModel):
    images: List[str] = Field(default_factory=list)
    passes: List[VerifyPass] = Field(default_factory=list)
    threshold: Optional[float] = None
    votes_yes: Optional[int] = None
    consensus_required: Optional[int] = None

    class Config:
        extra = "ignore"


class ReportPart(BaseModel):
    name: str
    location: Optional[str] = None
    severity: Severity = "minor"
    safety_critical: bool = False
    confidence: Optional[float] = None
    reason: Optional[str] = None  # for potential_parts
    votes: Optional[int] = Field(default=None, alias="_votes")
    verify: Optional[VerifyEvidence] = Field(default=None, alias="_verify")

    @validator("severity", pre=True, always=True)
    def _norm_report_severity(cls, v):  # type: ignore[no-untyped-def]
        if not v:
            return "minor"
        s = str(v).strip().lower()
        if s in ("severe", "high"):
            return "severe"
        if s in ("moderate", "medium"):
            return "moderate"
        return "minor"

    class Config:
        # pydantic v2: allow_population_by_field_name -> validate_by_name
        validate_by_name = True
        extra = "ignore"
