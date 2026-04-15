import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, status

from app.db.mongo import mongodb
from app.models.schemas import CropRecommendationResponse, RecommendationLog, SensorReadingInput
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "/hardware/{sensor_id}/readings",
    response_model=CropRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
async def create_hardware_recommendation(
    sensor_id: str = Path(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
    reading: SensorReadingInput = ...,
) -> CropRecommendationResponse:
    try:
        recommendation = await ai_service.recommend_crops(sensor_id=sensor_id, reading=reading)

        log_entry = RecommendationLog(
            sensor_id=sensor_id,
            timestamp=datetime.now(timezone.utc),
            input=reading,
            output=recommendation,
        )

        collection = mongodb.get_collection("recommendation_logs")
        await collection.insert_one(log_entry.model_dump(mode="json"))

        return recommendation
    except RuntimeError as exc:
        logger.exception("MongoDB is not connected.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Recommendation endpoint failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process recommendation request.",
        ) from exc
