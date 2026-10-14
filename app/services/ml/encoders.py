"""
Loader for the LabelEncoders produced by `tools.ingest features`.

Stored at: ai_models/ai_artifacts/price_encoders.pt
Format    : dict[str, sklearn.preprocessing.LabelEncoder] saved via torch.save.

Loading uses `weights_only=False` because LabelEncoder is an arbitrary Python
object (pickle), not a tensor. Only load files you produced yourself.
"""
from __future__ import annotations

from functools import lru_cache

import torch

from app.core.logging_config import logger
from app.core.request_id import get_request_id
from app.services.ml.config import ARTIFACTS_DIR


CATEGORICAL_COLS: tuple[str, ...] = (
    "brand",
    "model",
    "fuel_type",
    "transmission",
    "body_type",
)


@lru_cache(maxsize=1)
def get_encoders() -> dict:
    """Return the cached encoders dict, loading it on first call."""
    path = ARTIFACTS_DIR / "price_encoders.pt"
    if not path.exists():
        raise FileNotFoundError(
            f"Encoders not found at {path}. "
            f"Run `python -m tools.ingest features` first."
        )
    logger.info(
        "Encoders: loading",
        extra={"request_id": get_request_id(), "path": str(path)},
    )
    try:
        encoders = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        # PyTorch < 2.4 does not support weights_only.
        encoders = torch.load(path, map_location="cpu")
    return encoders