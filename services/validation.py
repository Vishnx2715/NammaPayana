"""
Validation models and startup data verification for Namma Payana.
Uses Pydantic v2 for strict schema guarantees and input hygiene.
"""
import datetime
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re as _re
import config

class BudgetInput(BaseModel):
    amount: Decimal = Field(..., description="Budget amount in given currency (must be positive)")
    scope: Literal["total", "per_person"] = Field("total", description="Whether budget applies to entire group or per person")
    currency: str = Field("INR", description="Currency code (INR default)")

    @field_validator("amount")
    @classmethod
    def validate_positive_budget(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Budget amount must be strictly greater than 0")
        return v

class JourneyDNA(BaseModel):
    start_city: str = Field(..., min_length=1, max_length=100)
    days: int = Field(..., ge=1, le=14, description="Trip duration between 1 and 14 days")
    travellers: int = Field(..., ge=1, le=20, description="Traveller party size between 1 and 20")
    budget: BudgetInput
    style: Literal["economical", "moderate", "luxury"] = Field("economical")
    interests: List[str] = Field(default_factory=list)
    pace: Literal["relaxed", "balanced", "packed"] = Field("balanced")
    transport: Literal["bus", "car", "train"] = Field("bus")
    stay: str = Field("budget")
    diet: str = Field("vegetarian")
    accessibility: List[str] = Field(default_factory=list)
    must_visit: List[str] = Field(default_factory=list)
    avoid: List[str] = Field(default_factory=list)
    start_date: Optional[str] = Field(None)

    @model_validator(mode="before")
    @classmethod
    def coerce_budget(cls, data):
        if isinstance(data, dict):
            b = data.get("budget")
            if isinstance(b, (int, float, str, Decimal)):
                data["budget"] = {"amount": b, "scope": "total", "currency": "INR"}
        return data

    @field_validator("start_city")
    @classmethod
    def validate_start_city(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("start_city cannot be empty or whitespace")
        return cleaned

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, v: List[str]) -> List[str]:
        if len(v) > 10:
            raise ValueError("interests must have at most 10 items")
        for item in v:
            if len(item) > 50:
                raise ValueError("each interest must be 50 characters or fewer")
        return v

    @field_validator("must_visit")
    @classmethod
    def validate_must_visit(cls, v: List[str]) -> List[str]:
        if len(v) > 24:
            raise ValueError("must_visit must have at most 24 items")
        for item in v:
            if len(item) > 100:
                raise ValueError("each must_visit entry must be 100 characters or fewer")
        return v

    @field_validator("avoid")
    @classmethod
    def validate_avoid(cls, v: List[str]) -> List[str]:
        if len(v) > 24:
            raise ValueError("avoid must have at most 24 items")
        return v

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            raise ValueError("start_date must be a valid ISO date string (YYYY-MM-DD)")
        return v

class ReplanRequest(BaseModel):
    dna: JourneyDNA
    changes: Optional[dict] = Field(default_factory=dict, description="Structured fields to update")
    instruction: Optional[str] = Field(None, max_length=500, description="Natural language prompt")

class TripSaveRequest(BaseModel):
    trip_id: Optional[str] = None
    edit_token: Optional[str] = None
    dna: JourneyDNA
    itinerary: dict
    cost_summary: dict
    uncertainties: Optional[List[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def extract_nested_trip(cls, data):
        if isinstance(data, dict):
            inner = data.get("trip_data") or data.get("trip")
            if isinstance(inner, dict):
                data.setdefault("dna", inner.get("dna"))
                data.setdefault("itinerary", inner.get("itinerary"))
                data.setdefault("cost_summary", inner.get("budget") or inner.get("cost_summary"))
                data.setdefault("uncertainties", inner.get("feasibility", {}).get("flags") or inner.get("uncertainties", []))
                if "id" in inner and not data.get("trip_id"):
                    data["trip_id"] = inner["id"]
        return data


class DestinationRecord(BaseModel):
    id: str = Field(..., min_length=2)
    name_en: str = Field(..., min_length=2)
    name_kn: str = Field(...)
    lat: float = Field(..., ge=config.KARNATAKA_LAT_MIN, le=config.KARNATAKA_LAT_MAX)
    lng: float = Field(..., ge=config.KARNATAKA_LNG_MIN, le=config.KARNATAKA_LNG_MAX)
    district: str
    region: str
    categories: List[str]
    description: str
    visit_hours: float = Field(..., gt=0.0)
    entry_fee_inr: dict
    accessibility_notes: dict
    best_season: dict
    image: dict
    sources: List[str]
    verification_status: Literal["verified", "partial", "unverified"]
    dataset_version: str
    opening_hours: Optional[str] = None
    closed_days: Optional[List[str]] = None

    @model_validator(mode="after")
    def check_entry_fee(self) -> "DestinationRecord":
        fee = self.entry_fee_inr
        if "basis" not in fee or fee["basis"] not in ["user_entered", "sourced", "estimated", "unknown"]:
            raise ValueError(f"Invalid entry fee basis in destination {self.id}")
        if fee.get("value") is not None and fee["value"] < 0:
            raise ValueError(f"Negative entry fee in destination {self.id}")
        return self


class TransitHub(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    type: Optional[str] = None
    nearest_destination_id: Optional[str] = None
    distance_km: Optional[float] = None
    operator: Optional[str] = None


class FoodPlace(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    cuisine: Optional[str] = None
    diet: Optional[str] = None
    price_tier: Optional[str] = None
    opening_hours: Optional[str] = None
    nearest_destination_id: Optional[str] = None
    distance_km: Optional[float] = None


# --- Password Strength Validation ---

COMMON_PASSWORDS = {
    "password", "12345678", "qwertyuiop", "iloveyou", "admin12345",
    "letmein123", "welcome123", "monkey1234", "football12", "baseball12",
    "dragon1234", "master1234", "superman12", "batman1234", "starwars12",
    "trustno112", "shadow1234", "michael123", "jessica123", "charlie123",
    "donald1234", "password1", "1234567890", "qwerty1234", "abc123456",
    "111111111", "123456789", "sunshine1", "princess1", "welcome12",
}


def validate_password_strength(password: str) -> None:
    """Raises ValueError if password fails strength requirements."""
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")
    if len(password) > 128:
        raise ValueError("Password must not exceed 128 characters.")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Password is too common. Please choose a stronger password.")
