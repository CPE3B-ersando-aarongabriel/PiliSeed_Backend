from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SensorReadingInput(BaseModel):
    temperature_c: float = Field(..., ge=-20.0, le=80.0)
    humidity_pct: float = Field(..., ge=0.0, le=100.0)
    soil_moisture_pct: float = Field(..., ge=0.0, le=100.0)
    light_lux: float = Field(..., ge=0.0, le=200000.0)


class CropRecommendationResponse(BaseModel):
    top_3_crops: list[str] = Field(..., min_length=3, max_length=3)
    message: str
    total_crops_generated: int = Field(..., ge=3)

    @field_validator("top_3_crops")
    @classmethod
    def normalize_crops(cls, crops: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()

        for crop in crops:
            value = crop.strip()
            if not value:
                continue
            lowered = value.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            unique.append(value)

        if len(unique) != 3:
            raise ValueError("top_3_crops must contain exactly 3 unique crop names.")

        return unique


class RecommendationLog(BaseModel):
    sensor_id: str
    timestamp: datetime
    input: SensorReadingInput
    output: CropRecommendationResponse
