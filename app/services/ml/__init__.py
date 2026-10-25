
from __future__ import annotations

__all__ = [
    "PriceInferenceService",
    "DamageInferenceService",
]


def __getattr__(name: str):
    """Lazy import — avoids pulling in torch/DB deps when only scalers are needed."""
    if name in __all__:
        from app.services.ml.training import inference as _inf
        return getattr(_inf, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")