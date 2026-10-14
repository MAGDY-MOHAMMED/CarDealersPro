"""
ML data pipeline for CarDealersPro.

Pure-PyTorch standardization (no sklearn, no joblib).

Exports:
    - TensorBundle          : validated (features, targets) tensor pair.
    - TorchStandardScaler   : PyTorch-native standard scaler.
    - StandardScalerBundle  : feature (+ optional target) scaler pair.
    - load_from_db          : read feature vectors from car_features table.
    - load_from_parquet     : fallback read from data/optimized/*.parquet.
    - load_best_available   : DB first, parquet fallback.
    - LoaderBundle          : train/val/test DataLoaders + metadata.
    - make_loaders          : reproducible split into DataLoaders.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pyarrow.parquet as pq
import torch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from torch import Tensor
from torch.utils.data import DataLoader, TensorDataset, random_split

from app.core.logging_config import logger
from app.core.request_id import get_request_id
from app.models import CarFeatures
from app.services.ml.config import (
    DATA_OPTIMIZED_DIR,
    INPUT_DIM,
    TARGET_COLUMN,
    SplitConfig,
    TrainingConfig,
)


# =====================================================================
# 1. TensorBundle
# =====================================================================
@dataclass(frozen=True, slots=True)
class TensorBundle:
    """
    Immutable (features, targets) tensor pair.

    Invariants (validated at construction):
        - features is 2D: (n_samples, input_dim)
        - targets is 1D or 2D; if 1D it is reshaped to (n_samples, 1)
        - features.shape[0] == targets.shape[0]
        - features.device.type == targets.device.type
    """

    features: Tensor
    targets: Tensor
    device: torch.device | None = None  # derived from features.device if omitted

    def __post_init__(self) -> None:
        if self.features.dim() != 2:
            raise ValueError(
                f"features must be 2D (n_samples, input_dim), "
                f"got {tuple(self.features.shape)}"
            )
        targets = self.targets
        if targets.dim() == 1:
            targets = targets.unsqueeze(1)
        elif targets.dim() != 2:
            raise ValueError(
                f"targets must be 1D or 2D, got {tuple(targets.shape)}"
            )
        if self.features.shape[0] != targets.shape[0]:
            raise ValueError(
                f"features/targets row mismatch: "
                f"{self.features.shape[0]} vs {targets.shape[0]}"
            )
        if self.features.device.type != targets.device.type:
            raise ValueError(
                f"features/targets device mismatch: "
                f"{self.features.device} vs {targets.device}"
            )
        object.__setattr__(self, "targets", targets)
        object.__setattr__(
            self,
            "device",
            torch.device(self.device)
            if self.device is not None
            else self.features.device,
        )

    @property
    def n_samples(self) -> int:
        return int(self.features.shape[0])

    @property
    def input_dim(self) -> int:
        return int(self.features.shape[1])

    @property
    def target_dim(self) -> int:
        return int(self.targets.shape[1])


# =====================================================================
# 2. TorchStandardScaler  (pure PyTorch)
# =====================================================================
class TorchStandardScaler:
    """
    PyTorch-native standard scaler.

    Computes per-feature mean and population std (unbiased=False, ddof=0),
    then standardizes:  x_scaled = (x - mean) / std.

    Stats are stored as float32 tensors on CPU, so the artifact is
    portable across devices and environments.

    Usage:
        scaler = TorchStandardScaler.fit(X)      # X: (n, d) Tensor
        Xs     = scaler.transform(X)
        X_back = scaler.inverse_transform(Xs)
    """

    def __init__(self, mean: Tensor, std: Tensor, eps: float = 1e-8) -> None:
        if mean.dim() != 1 or std.dim() != 1:
            raise ValueError(
                f"mean/std must be 1D tensors, got {mean.shape} / {std.shape}"
            )
        if mean.shape != std.shape:
            raise ValueError(
                f"mean/std shape mismatch: {mean.shape} vs {std.shape}"
            )
        # Force CPU + float32 for portability.
        self.mean: Tensor = mean.detach().to(dtype=torch.float32, device="cpu").clone()
        self.std: Tensor = (
            std.detach()
            .to(dtype=torch.float32, device="cpu")
            .clamp_min(eps)
            .clone()
        )
        self.eps: float = float(eps)

    # -------- fitting --------
    @classmethod
    def fit(cls, X: Tensor, eps: float = 1e-8) -> "TorchStandardScaler":
        if X.dim() != 2:
            raise ValueError(
                f"X must be 2D (n_samples, n_features), got {tuple(X.shape)}"
            )
        X = X.detach().to(dtype=torch.float32, device="cpu")
        mean = X.mean(dim=0)
        # unbiased=False -> population std (matches numpy ddof=0 / sklearn default).
        std = X.std(dim=0, unbiased=False)
        return cls(mean=mean, std=std, eps=eps)

    # -------- transforms --------
    def transform(self, X: Tensor) -> Tensor:
        if X.dim() != 2:
            raise ValueError(f"X must be 2D, got {tuple(X.shape)}")
        if X.shape[1] != self.n_features:
            raise ValueError(
                f"X has {X.shape[1]} features, scaler expects {self.n_features}"
            )
        mean = self.mean.to(X.device, dtype=X.dtype)
        std = self.std.to(X.device, dtype=X.dtype)
        return (X - mean) / std

    def inverse_transform(self, X: Tensor) -> Tensor:
        if X.dim() != 2:
            raise ValueError(f"X must be 2D, got {tuple(X.shape)}")
        if X.shape[1] != self.n_features:
            raise ValueError(
                f"X has {X.shape[1]} features, scaler expects {self.n_features}"
            )
        mean = self.mean.to(X.device, dtype=X.dtype)
        std = self.std.to(X.device, dtype=X.dtype)
        return X * std + mean

    # -------- serialization --------
    def state_dict(self) -> dict:
        return {
            "mean": self.mean.clone(),
            "std": self.std.clone(),
            "eps": self.eps,
        }

    @classmethod
    def from_state_dict(cls, sd: dict) -> "TorchStandardScaler":
        return cls(
            mean=sd["mean"],
            std=sd["std"],
            eps=float(sd.get("eps", 1e-8)),
        )

    # -------- helpers --------
    @property
    def n_features(self) -> int:
        return int(self.mean.shape[0])


# =====================================================================
# 3. StandardScalerBundle
# =====================================================================
class StandardScalerBundle:
    """
    Pairs a feature scaler with an optional target scaler.

    Why a bundle:
        - A trained price model must be paired with the EXACT scaler used
          at training time; shipping one without the other silently
          produces garbage predictions.
        - The target scaler is optional: if training used raw prices as the
          target, then `target_scaler=None` and inverse-transform is identity.

    Persistence:
        Saved as a single `.pt` file via `torch.save`. Payload is a plain
        dict of tensors/primitives (safe to load with `weights_only=True`).
    """

    def __init__(
        self,
        feature_scaler: TorchStandardScaler,
        target_scaler: Optional[TorchStandardScaler] = None,
    ) -> None:
        self.feature_scaler = feature_scaler
        self.target_scaler = target_scaler

    # -------- fitting --------
    @classmethod
    def fit(
        cls,
        X: Tensor,
        y: Optional[Tensor] = None,
    ) -> "StandardScalerBundle":
        feature_scaler = TorchStandardScaler.fit(X)
        target_scaler = None
        if y is not None:
            y2d = y.reshape(-1, 1) if y.dim() == 1 else y
            target_scaler = TorchStandardScaler.fit(y2d)
        return cls(feature_scaler=feature_scaler, target_scaler=target_scaler)

    # -------- transforms --------
    def transform_features(self, X: Tensor) -> Tensor:
        return self.feature_scaler.transform(X)

    def transform_targets(self, y: Tensor) -> Tensor:
        y2d = y.reshape(-1, 1) if y.dim() == 1 else y
        if self.target_scaler is None:
            return y2d
        return self.target_scaler.transform(y2d)

    def inverse_transform_targets(self, y: Tensor) -> Tensor:
        y2d = y.reshape(-1, 1) if y.dim() == 1 else y
        if self.target_scaler is None:
            return y2d
        return self.target_scaler.inverse_transform(y2d)

    # Alias kept so any old caller that used the sklearn-style API still works.
    def transform(self, X: Tensor) -> Tensor:
        return self.transform_features(X)

    # -------- serialization --------
    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": 1,
            "feature_scaler": self.feature_scaler.state_dict(),
            "target_scaler": (
                self.target_scaler.state_dict()
                if self.target_scaler is not None
                else None
            ),
        }
        torch.save(payload, path)
        logger.info(
            "StandardScalerBundle: saved",
            extra={"request_id": get_request_id(), "path": str(path)},
        )

    @classmethod
    def load(
        cls,
        path: Path | str,
        map_location: str = "cpu",
    ) -> "StandardScalerBundle":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Scaler bundle not found at {path}")

        try:
            payload = torch.load(path, map_location=map_location, weights_only=True)
        except TypeError:
            # Older PyTorch (< 2.4) does not support `weights_only`.
            payload = torch.load(path, map_location=map_location)

        if not isinstance(payload, dict) or "feature_scaler" not in payload:
            raise TypeError(
                f"Unsupported scaler artifact at {path}. "
                f"Expected a dict produced by StandardScalerBundle.save(). "
                f"If this is an old joblib/sklearn file, re-run "
                f"`python -m tools.ingest features` to regenerate it."
            )

        feature_scaler = TorchStandardScaler.from_state_dict(payload["feature_scaler"])
        target_scaler = None
        if payload.get("target_scaler") is not None:
            target_scaler = TorchStandardScaler.from_state_dict(payload["target_scaler"])

        return cls(feature_scaler=feature_scaler, target_scaler=target_scaler)

    # -------- helpers --------
    @property
    def n_features(self) -> int:
        return self.feature_scaler.n_features

    @property
    def has_target_scaler(self) -> bool:
        return self.target_scaler is not None


# =====================================================================
# 4. Data loaders
# =====================================================================
async def load_from_db(
    session: AsyncSession,
    device: torch.device,
    *,
    min_rows: int = 100,
) -> TensorBundle:
    """
    Load feature vectors from the 'car_features' table.

    Expects:
        - `feature_vector` is a non-null ARRAY(Float) column (PostgreSQL)
        - `predicted_price` is populated (used as the regression target
          until real sale prices are collected).

    Raises RuntimeError if fewer than `min_rows` valid rows exist.
    """
    request_id = get_request_id()
    logger.info(
        "ML data load: querying car_features",
        extra={"request_id": request_id, "source": "postgres"},
    )

    stmt = (
        select(CarFeatures.feature_vector, CarFeatures.predicted_price)
        .where(CarFeatures.feature_vector.isnot(None))
        .where(CarFeatures.predicted_price.isnot(None))
    )
    result = await session.execute(stmt)
    rows = result.all()

    if len(rows) < min_rows:
        raise RuntimeError(
            f"car_features has only {len(rows)} valid rows; need >= {min_rows}. "
            f"Run `python -m import_data.generate_parquet` and sync via "
            f"`core/data_sync.py`."
        )

    # Vectorize: build (N, D) float32 array in one shot.
    features_np = np.asarray([r[0] for r in rows], dtype=np.float32, order="C")
    targets_np = np.asarray(
        [[float(r[1])] for r in rows], dtype=np.float32, order="C"
    )

    if features_np.shape[1] != INPUT_DIM:
        raise RuntimeError(
            f"feature_vector has dim {features_np.shape[1]}, expected {INPUT_DIM}. "
            f"Update FEATURE_COLUMNS in config.py."
        )

    logger.info(
        "ML data load: DB ready",
        extra={
            "request_id": request_id,
            "n_samples": int(features_np.shape[0]),
            "input_dim": int(features_np.shape[1]),
        },
    )
    return TensorBundle(
        features=torch.from_numpy(features_np).to(device, non_blocking=True),
        targets=torch.from_numpy(targets_np).to(device, non_blocking=True),
    )


def load_from_parquet(
    parquet_dir: Path,
    device: torch.device,
    *,
    filename: str = "car_features.parquet",
) -> TensorBundle:
    """Fallback loader from parquet (pyarrow -> numpy -> torch)."""
    request_id = get_request_id()
    path = parquet_dir / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Parquet not found at {path}. Run `python -m tools.ingest features` first."
        )

    logger.info(
        "ML data load: reading parquet",
        extra={"request_id": request_id, "path": str(path)},
    )

    df = pq.read_table(path).to_pandas()

    # `features` column stores list[float] per row.
    features_np = np.asarray(df["features"].tolist(), dtype=np.float32, order="C")
    targets_np = np.asarray(
        df[TARGET_COLUMN].to_numpy().reshape(-1, 1),
        dtype=np.float32,
        order="C",
    )

    logger.info(
        "ML data load: parquet ready",
        extra={
            "request_id": request_id,
            "n_samples": int(features_np.shape[0]),
        },
    )
    return TensorBundle(
        features=torch.from_numpy(features_np).to(device, non_blocking=True),
        targets=torch.from_numpy(targets_np).to(device, non_blocking=True),
    )


async def load_best_available(
    session: Optional[AsyncSession],
    device: torch.device,
) -> TensorBundle:
    """DB first; parquet as fallback. Logs which path was taken."""
    if session is not None:
        try:
            return await load_from_db(session, device)
        except Exception as exc:
            logger.warning(
                "ML data load: DB failed, falling back to parquet",
                extra={"request_id": get_request_id(), "error": str(exc)},
            )
    return await asyncio.to_thread(load_from_parquet, DATA_OPTIMIZED_DIR, device)


# =====================================================================
# 5. LoaderBundle + make_loaders
# =====================================================================
@dataclass(frozen=True, slots=True)
class LoaderBundle:
    """Train/val/test DataLoaders plus metadata."""

    train: DataLoader
    val: DataLoader
    test: DataLoader
    train_size: int
    val_size: int
    test_size: int
    input_dim: int
    target_dim: int
    device: torch.device


def make_loaders(
    bundle: TensorBundle,
    train_cfg: TrainingConfig,
    split_cfg: SplitConfig,
    *,
    seed: int = 42,
    shuffle_train: bool = True,
) -> LoaderBundle:
    """
    Build reproducible train/val/test DataLoaders.

    Guarantees:
        - No CPU<->GPU transfer inside this function (bundle already on device).
        - Deterministic split via local Generator.
        - Windows-safe: num_workers must be 0 on win32 (enforced here).
    """
    n = bundle.n_samples
    if n < 3:
        raise ValueError(f"Need at least 3 samples, got {n}")

    n_train = int(n * split_cfg.train)
    n_val = int(n * split_cfg.val)
    n_test = n - n_train - n_val
    if min(n_train, n_val, n_test) < 1:
        raise RuntimeError(
            f"Split produced empty subset: train={n_train}, val={n_val}, test={n_test}"
        )

    if sys.platform == "win32" and train_cfg.num_workers > 0:
        raise ValueError(
            "On Windows, set TrainingConfig.num_workers=0 unless the caller "
            "wraps everything in `if __name__ == '__main__':`."
        )

    generator = torch.Generator(device="cpu").manual_seed(seed)
    dataset = TensorDataset(bundle.features, bundle.targets)
    train_ds, val_ds, test_ds = random_split(
        dataset, [n_train, n_val, n_test], generator=generator
    )

    # NOTE: use bundle.device (TrainingConfig has no `device` attribute).
    pin = train_cfg.pin_memory and bundle.device.type == "cuda"

    common_kwargs: dict = {
        "batch_size": train_cfg.batch_size,
        "num_workers": train_cfg.num_workers,
        "pin_memory": pin,
        "persistent_workers": (
            train_cfg.persistent_workers and train_cfg.num_workers > 0
        ),
    }
    # prefetch_factor is only supported when num_workers > 0 and not on Windows.
    if train_cfg.num_workers > 0 and sys.platform != "win32":
        common_kwargs["prefetch_factor"] = train_cfg.prefetch_factor

    train_loader = DataLoader(
        train_ds, shuffle=shuffle_train, drop_last=True, **common_kwargs
    )
    val_loader = DataLoader(val_ds, shuffle=False, drop_last=False, **common_kwargs)
    test_loader = DataLoader(test_ds, shuffle=False, drop_last=False, **common_kwargs)

    logger.info(
        "ML loaders: built",
        extra={
            "request_id": get_request_id(),
            "train": n_train,
            "val": n_val,
            "test": n_test,
            "batch_size": train_cfg.batch_size,
            "num_workers": train_cfg.num_workers,
            "device": str(bundle.device),
        },
    )

    return LoaderBundle(
        train=train_loader,
        val=val_loader,
        test=test_loader,
        train_size=n_train,
        val_size=n_val,
        test_size=n_test,
        input_dim=bundle.input_dim,
        target_dim=bundle.target_dim,
        device=bundle.device,
    )