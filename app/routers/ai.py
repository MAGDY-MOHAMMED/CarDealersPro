"""
AI router for CarDealersPro.

Exposes:
    - POST /ai/price-predict
    - POST /ai/inspect-image

Both endpoints delegate to the singleton services in `app.services.ml.inference`.
"""

from __future__ import annotations

import torch
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.logging_config import logger
from app.core.request_id import get_request_id
from app.core.security import get_auth_user
from app.schemas import (
    ImageInspectResponse,
    PricePredictRequest,
    PricePredictResponse,
    RawCarFeatures,
    TokenData,

)
from app.services.ml.encoders import CATEGORICAL_COLS, get_encoders
from app.services.ml.config import FEATURE_COLUMNS
from app.services.ml.training.inference import DamageInferenceService, PriceInferenceService

router = APIRouter(prefix="/ai", tags=["AI"])


MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


@router.post(
    "/price-predict",
    response_model=PricePredictResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_price(
    payload: PricePredictRequest,
    _: TokenData = Depends(get_auth_user),
) -> PricePredictResponse:
    """
    Predict a fair price for a car based on its features.

    NOTE: the caller is expected to have already transformed the raw features
    (brand → brand_enc, etc.) — the API takes already-encoded values.
    """
    # Build a (1, INPUT_DIM) tensor in the exact column order the model expects.
    # Any mismatch here silently corrupts predictions, so we assert per column.
    feature_dict = payload.model_dump()
    missing = [c for c in FEATURE_COLUMNS if c not in feature_dict]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing features: {missing}",
        )

    x = torch.tensor(
        [[float(feature_dict[c]) for c in FEATURE_COLUMNS]],
        dtype=torch.float32,
    )

    try:
        result = PriceInferenceService().predict(x)
    except Exception as exc:
        logger.error(
            "Price prediction failed",
            extra={"request_id": get_request_id(), "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Price prediction failed",
        )

    logger.info(
        "Price prediction served",
        extra={
            "request_id": get_request_id(),
            "predicted_price": result["predicted_price"],
        },
    )
    return PricePredictResponse(**result)


@router.post(
    "/encode",
    response_model=PricePredictRequest,
    status_code=status.HTTP_200_OK,
)
async def encode_car_features(
    payload: RawCarFeatures,
    _: TokenData = Depends(get_auth_user),
) -> PricePredictRequest:
    """
    Translate raw (human-readable) car features into the encoded integer
    form expected by POST /ai/price-predict.

    Uses the exact LabelEncoders saved at training time, so the result is
    guaranteed to match what the model was trained on.
    """
    try:
        encoders = get_encoders()
    except FileNotFoundError as exc:
        logger.error(
            "Encoders missing",
            extra={"request_id": get_request_id(), "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Encoders not available yet. "
                "Run `python -m tools.ingest features` first."
            ),
        )

    encoded_fields: dict[str, int] = {}
    errors: list[str] = []

    for col in CATEGORICAL_COLS:
        # ingest.py lowercases everything; mirror that exactly.
        raw_value = getattr(payload, col).strip().lower()

        le = encoders.get(col)
        if le is None:
            errors.append(f"Encoder for '{col}' is missing from artifacts.")
            continue

        try:
            encoded_fields[f"{col}_enc"] = int(le.transform([raw_value])[0])
        except ValueError:
            known = list(le.classes_)
            # Cap the hint size so error payloads stay small.
            preview = known[:20]
            hint = ", ".join(preview) + (" ..." if len(known) > 20 else "")
            errors.append(
                f"Unknown value '{raw_value}' for '{col}'. "
                f"Known values: {hint}"
            )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ENCODING_FAILED", "errors": errors},
        )

    return PricePredictRequest(
        year=payload.year,
        mileage=payload.mileage,
        **encoded_fields,
    )


@router.post(
    "/inspect-image",
    response_model=ImageInspectResponse,
    status_code=status.HTTP_200_OK,
)
async def inspect_image(
    file: UploadFile = File(...),
    _: TokenData = Depends(get_auth_user),
) -> ImageInspectResponse:
    """Detect damage in a car image."""
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type: {file.content_type}",
        )

    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )

    try:
        result = DamageInferenceService().inspect(content)
    except Exception as exc:
        logger.error(
            "Image inspection failed",
            extra={"request_id": get_request_id(), "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image inspection failed",
        )

    logger.info(
        "Image inspection served",
        extra={
            "request_id": get_request_id(),
            "damage_pct": result["damage_percentage"],
        },
    )
    return ImageInspectResponse(**result)