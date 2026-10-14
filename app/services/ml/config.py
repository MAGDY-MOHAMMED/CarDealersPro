from __future__ import annotations

from app.core.config import BASE_DIR

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Tuple, Optional

# Path configuration
MODELS_DIR: Final[Path] = BASE_DIR / "ai_models"
ARTIFACTS_DIR: Final[Path] = MODELS_DIR / "artifacts"
DATA_OPTIMIZED_DIR: Final[Path] = BASE_DIR / "data" / "optimized"

# Create directories if missing
MODELS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)


FEATURE_COLUMNS: Final[Tuple[str, ...]] = (
    "year",
    "mileage",
    "brand_enc",
    "model_enc",
    "fuel_type_enc",
    "transmission_enc",
    "body_type_enc",
)

TARGET_COLUMN: Final[str] = "price_prediction"
DAMAGE_COLUMN: Final[str] = "damage_score"

INPUT_DIM: Final[int] = len(FEATURE_COLUMNS)


@dataclass(frozen=True, slots=True)
class PriceModelConfig:
    """
    Configuration for PriceRegressor.

    Defaults are tuned for the CarDealersPro dataset scale:
        - `hidden_dims=(256, 256, 128, 128, 64)` activates real
        residual shortcuts at depths 1<->2 and 3<->4.
        - Keeping the previous default `(256, 128, 64)` silently builds a
        plain MLP with no residual blocks - the docstring in
        `price_regressor.py` explicitly warns against this.
    """
    input_dim: int = INPUT_DIM
    hidden_dims: Tuple[int, ...] = (256, 256, 128, 128, 64)
    dropout: float = 0.15
    use_layernorm: bool = True
    activation: str = "gelu"


@dataclass(frozen=True, slots=True)
class DamageModelConfig:
    num_classes: int = 4
    backbone: str = "resnet18"
    pretrained: bool = True
    freeze_backbone: bool = True
    dropout: float = 0.2
    head_hidden: Optional[int] = None


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    batch_size: int = 64
    num_workers: int = 0
    pin_memory: bool = True
    persistent_workers: bool = True
    prefetch_factor: int = 2
    lr: float = 3e-4
    weight_decay: float = 1e-4
    epochs: int = 50
    grad_clip_norm: float = 1.0
    early_stop_patience: int = 8
    scheduler: str = "cosine"
    seed: int = 42
    amp: bool = True
    log_every_n_steps: int = 50


@dataclass(frozen=True, slots=True)
class SplitConfig:
    train: float = 0.8
    val: float = 0.1
    test: float = 0.1

    def __post_init__(self) -> None:
        total = self.train + self.val + self.test
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"split ratios must sum to 1.0, got {total:.6f}")