import json
import logging
from json import JSONDecodeError

from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.core.config import settings
from app.models.schemas import CropRecommendationResponse, SensorReadingInput

logger = logging.getLogger(__name__)


class AIService:
    philippines_priority_crops = [
        "Palay",
        "Mais",
        "Talong",
        "Kamatis",
        "Okra",
        "Sitaw",
        "Kangkong",
        "Ampalaya",
        "Sili",
        "Bawang",
        "Sibuyas",
        "Kamoote",
        "Ubi",
        "Gabi",
        "Mani",
        "Saging",
        "Manga",
        "Pinya",
        "Cassava",
        "Niyog",
    ]

    crop_aliases = {
        "palay": "Palay",
        "rice": "Palay",
        "mais": "Mais",
        "corn": "Mais",
        "maize": "Mais",
        "talong": "Talong",
        "eggplant": "Talong",
        "kamatis": "Kamatis",
        "tomato": "Kamatis",
        "okra": "Okra",
        "sitaw": "Sitaw",
        "string bean": "Sitaw",
        "string beans": "Sitaw",
        "yardlong bean": "Sitaw",
        "kangkong": "Kangkong",
        "water spinach": "Kangkong",
        "ampalaya": "Ampalaya",
        "bitter gourd": "Ampalaya",
        "bitter melon": "Ampalaya",
        "sili": "Sili",
        "chili": "Sili",
        "chili pepper": "Sili",
        "chilli": "Sili",
        "bawang": "Bawang",
        "garlic": "Bawang",
        "sibuyas": "Sibuyas",
        "onion": "Sibuyas",
        "kamoote": "Kamoote",
        "kamote": "Kamoote",
        "sweet potato": "Kamoote",
        "ubi": "Ubi",
        "ube": "Ubi",
        "yam": "Ubi",
        "gabi": "Gabi",
        "taro": "Gabi",
        "mani": "Mani",
        "peanut": "Mani",
        "groundnut": "Mani",
        "saging": "Saging",
        "banana": "Saging",
        "manga": "Manga",
        "mango": "Manga",
        "pinya": "Pinya",
        "pineapple": "Pinya",
        "cassava": "Cassava",
        "kamoteng kahoy": "Cassava",
        "niyog": "Niyog",
        "coconut": "Niyog",
    }

    default_crops = ["Palay", "Mais", "Talong"]

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self._allowed_crop_map = {
            crop.lower(): crop for crop in self.philippines_priority_crops
        }
        for alias, canonical in self.crop_aliases.items():
            self._allowed_crop_map[alias.lower()] = canonical

        if settings.openai_api_key:
            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout_seconds,
            )
        else:
            logger.warning("OPENAI_API_KEY not configured. Heuristic fallback will be used.")

    async def recommend_crops(
        self,
        sensor_id: str,
        reading: SensorReadingInput,
    ) -> CropRecommendationResponse:
        if self._client is None:
            return self._build_fallback_response(
                reading=reading,
                reason="Walang AI key, kaya emergency fallback ang ginamit.",
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(sensor_id=sensor_id, reading=reading)

        try:
            completion = await self._client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.15,
                max_tokens=220,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw_content = completion.choices[0].message.content or "{}"
            payload = self._parse_json_payload(raw_content)

            crops = self._sanitize_crops(payload.get("top_3_crops"), reading)
            message = self._sanitize_message(
                payload.get("message"),
                default_message="Batay sa reading, ito ang pinaka-angkop na pananim ngayon.",
            )

            return CropRecommendationResponse(
                top_3_crops=crops,
                message=message,
                total_crops_generated=3,
            )
        except APITimeoutError:
            logger.warning("OpenAI request timed out.")
            return self._build_fallback_response(
                reading=reading,
                reason="Mabagal ang AI response, kaya emergency fallback muna.",
            )
        except (OpenAIError, JSONDecodeError, KeyError, TypeError, ValueError):
            logger.exception("OpenAI recommendation generation failed.")
            return self._build_fallback_response(
                reading=reading,
                reason="Nagkaproblema sa AI output, kaya emergency fallback muna.",
            )
        except Exception:
            logger.exception("Unexpected recommendation error.")
            return self._build_fallback_response(
                reading=reading,
                reason="May hindi inaasahang error, kaya emergency fallback muna.",
            )

    def _build_system_prompt(self) -> str:
        allowed_crops_text = ", ".join(self.philippines_priority_crops)
        return (
            "You are PiliSeed AI, an expert Filipino crop recommendation engine for a low-power ESP32 smart agriculture device operating in the Philippines, and you must analyze real farm sensor inputs in practical terms for tropical, humid, monsoon-driven local conditions experienced by smallholder farmers, backyard growers, and municipal farm users; your decisions must prioritize Philippine crop suitability, realistic field viability, and farmer readability over scientific verbosity, and your output crops must default to Filipino or commonly used local names such as Palay, Mais, Talong, Kamatis, Okra, Sitaw, Kangkong, Ampalaya, Sili, Bawang, Sibuyas, Kamoote, Ubi, Gabi, Mani, Saging, Manga, Pinya, Cassava, and Niyog, using English aliases only when necessary for clarity; interpret temperature_c, humidity_pct, soil_moisture_pct, and light_lux as real-time agronomic signals from a button-triggered IoT device and rank exactly three crops from most suitable to least suitable based on current conditions, favoring moisture-tolerant crops when humidity and soil moisture are high, heat and drought-tolerant crops when soil moisture is low and light is strong, and common Filipino vegetables when warm conditions are balanced, while avoiding unrealistic imported, greenhouse-only, or non-tropical crops unless strongly justified by the readings; you may treat external crop references such as Trefle as secondary context only, never as final authority, because final selection must always prioritize Philippine locality and practical planting conditions; your response is for OLED and simple mobile display so keep names short, avoid long phrases, avoid duplicates, and keep the explanation brief and operational in simple Filipino or Filipino-English; return only valid JSON with exactly these keys and no extras: top_3_crops (array of exactly 3 unique strings), message (short explanation), total_crops_generated (integer 3), and never output markdown, code fences, prose outside JSON, or malformed JSON. Allowed crop pool: "
            f"{allowed_crops_text}."
        )

    def _build_user_prompt(self, sensor_id: str, reading: SensorReadingInput) -> str:
        return (
            "PiliSeed ESP32 live reading from a Philippine farm. "
            f"sensor_id={sensor_id}, "
            f"temperature_c={reading.temperature_c}, "
            f"humidity_pct={reading.humidity_pct}, "
            f"soil_moisture_pct={reading.soil_moisture_pct}, "
            f"light_lux={reading.light_lux}. "
            "Return ranked top_3_crops for immediate planting guidance using Filipino crop names whenever possible."
        )

    def _parse_json_payload(self, raw_content: str) -> dict:
        try:
            return json.loads(raw_content)
        except JSONDecodeError:
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return json.loads(raw_content[start : end + 1])

    def _sanitize_crops(self, raw_crops: object, reading: SensorReadingInput) -> list[str]:
        crops: list[str] = []
        seen: set[str] = set()

        if isinstance(raw_crops, list):
            for item in raw_crops:
                if not isinstance(item, str):
                    continue
                canonical = self._normalize_allowed_crop(item)
                if canonical and canonical.lower() not in seen:
                    seen.add(canonical.lower())
                    crops.append(canonical)

                if len(crops) == 3:
                    break

        if len(crops) < 3:
            for fallback_crop in self._emergency_candidates(reading):
                canonical = self._normalize_allowed_crop(fallback_crop)
                if canonical and canonical.lower() not in seen:
                    seen.add(canonical.lower())
                    crops.append(canonical)
                if len(crops) == 3:
                    break

        if len(crops) < 3:
            for default_crop in self.default_crops:
                canonical = self._normalize_allowed_crop(default_crop)
                if canonical and canonical.lower() not in seen:
                    seen.add(canonical.lower())
                    crops.append(canonical)
                if len(crops) == 3:
                    break

        if len(crops) < 3:
            for local_crop in self.philippines_priority_crops:
                if local_crop.lower() not in seen:
                    seen.add(local_crop.lower())
                    crops.append(local_crop)
                if len(crops) == 3:
                    break

        return crops[:3]

    def _normalize_allowed_crop(self, crop_name: str) -> str | None:
        key = crop_name.strip().lower()
        return self._allowed_crop_map.get(key)

    def _sanitize_message(self, raw_message: object, default_message: str) -> str:
        if isinstance(raw_message, str):
            compact = " ".join(raw_message.split())
            if compact:
                return compact[:180]
        return default_message

    def _build_fallback_response(
        self,
        reading: SensorReadingInput,
        reason: str,
    ) -> CropRecommendationResponse:
        crops = self._emergency_candidates(reading)[:3]
        return CropRecommendationResponse(
            top_3_crops=crops,
            message=self._sanitize_message(reason, "Emergency fallback recommendation."),
            total_crops_generated=3,
        )

    def _emergency_candidates(self, reading: SensorReadingInput) -> list[str]:
        if reading.soil_moisture_pct >= 65 and reading.humidity_pct >= 65:
            return ["Palay", "Kangkong", "Gabi"]

        if reading.soil_moisture_pct <= 35 and reading.light_lux >= 45000:
            return ["Mais", "Kamoote", "Mani"]

        if 22 <= reading.temperature_c <= 32 and 40 <= reading.humidity_pct <= 85:
            return ["Talong", "Kamatis", "Okra"]

        return ["Sitaw", "Ampalaya", "Sili"]


ai_service = AIService()
