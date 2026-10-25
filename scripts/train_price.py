"""
Training script for the price regression model.

Usage (from the project root):

    python -m scripts.train_price
    python -m scripts.train_price --epochs 100 --batch-size 128
    python -m scripts.train_price --device cpu
    python -m scripts.train_price --device cuda --run-name price_v2

What it does:
    1. Loads feature vectors + target prices from DB (parquet fallback).
    2. Fits a StandardScalerBundle on the features (target stays raw EGP).
    3. Persists the scaler to ai_models/ai_artifacts/price_scaler.pt.
    4. Splits into train/val/test and builds DataLoaders.
    5. Trains a PriceRegressor with EarlyStopping + loss-curve callback.
    6. Saves the final model to ai_models/ai_artifacts/price_model.pt.

The scaler is saved BEFORE training starts so that even if training crashes
mid-way, the exact preprocessing is on disk for reproducibility.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import torch
from torch import nn

# Allow running as `python scripts/train_price.py` directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.logging_config import logger
from app.core.request_id import generate_request_id, get_request_id, set_request_id
from app.database import PrimarySessionLocal
from app.services.ml.config import (
    ARTIFACTS_DIR,
    PriceModelConfig,
    SplitConfig,
    TrainingConfig,
)
from app.services.ml.data_pipeline import (
    StandardScalerBundle,
    TensorBundle,
    load_best_available,
    make_loaders,
)
from app.services.ml.models.price_regressor import PriceRegressor
from app.services.ml.training.callbacks import EarlyStopping, LossCurveCallback
from app.services.ml.training.loop import Trainer


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def pick_device(prefer: str) -> torch.device:
    """Resolve --device into a torch.device, with a helpful error on cuda."""
    if prefer == "cpu":
        return torch.device("cpu")
    if prefer == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA requested but not available. "
                "Install a CUDA-enabled torch wheel or use --device cpu."
            )
        return torch.device("cuda")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


async def _load_raw_bundle(device: torch.device) -> TensorBundle:
    """Open a DB session and let data_pipeline pick DB-first / parquet-fallback."""
    async with PrimarySessionLocal() as session:
        return await load_best_available(session, device)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def main_async(args: argparse.Namespace) -> int:
    set_request_id(generate_request_id())
    device = pick_device(args.device)

    logger.info(
        "train_price: starting",
        extra={
            "request_id": get_request_id(),
            "device": str(device),
            "run_name": args.run_name,
            "epochs": args.epochs,
        },
    )

    # ---- 1. Load raw (unscaled) data ----
    raw_bundle = await _load_raw_bundle(device)
    logger.info(
        "train_price: data loaded",
        extra={
            "request_id": get_request_id(),
            "n_samples": raw_bundle.n_samples,
            "input_dim": raw_bundle.input_dim,
        },
    )

    # ---- 2. Fit scaler on features only (target stays raw EGP) ----
    scaler_bundle = StandardScalerBundle.fit(raw_bundle.features)
    scaled_features = scaler_bundle.transform_features(raw_bundle.features)
    bundle = TensorBundle(
        features=scaled_features,
        targets=raw_bundle.targets,
        device=device,
    )

    # ---- 3. Persist scaler BEFORE training (crash-safe) ----
    scaler_path = ARTIFACTS_DIR / "price_scaler.pt"
    scaler_bundle.save(scaler_path)

    # ---- 4. Build loaders ----
    train_cfg = TrainingConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        lr=args.lr,
        seed=args.seed,
        amp=args.amp,
    )
    split_cfg = SplitConfig()
    loaders = make_loaders(bundle, train_cfg, split_cfg, seed=args.seed)

    # ---- 5. Model + criterion + callbacks ----
    model = PriceRegressor(PriceModelConfig()).to(device)
    model.describe("PriceRegressor")

    # HuberLoss on RAW EGP targets — robust to outliers. Loss magnitudes will
    # look huge (~1e5) because EGP prices are in the hundreds of thousands.
    criterion = nn.HuberLoss(delta=1.0)

    callbacks = [
        EarlyStopping(
            patience=train_cfg.early_stop_patience,
            checkpoint_name="best.pt",
        ),
        LossCurveCallback(run_name=args.run_name),
    ]

    # ---- 6. Train ----
    trainer = Trainer(
        model=model,
        train_loader=loaders.train,
        val_loader=loaders.val,
        criterion=criterion,
        cfg=train_cfg,
        device=device,
        run_name=args.run_name,
        callbacks=callbacks,
    )
    state = trainer.fit()

    # ---- 7. Save final model + report ----
    model_path = ARTIFACTS_DIR / "price_model.pt"
    model.save(model_path)

    logger.info(
        "train_price: done",
        extra={
            "request_id": get_request_id(),
            "model_path": str(model_path),
            "scaler_path": str(scaler_path),
            "best_val_loss": round(state.best_val_loss, 6),
            "final_epoch": state.epoch,
        },
    )
    print(f"\nModel  : {model_path}")
    print(f"Scaler : {scaler_path}")
    print(f"Best val loss: {state.best_val_loss:.6f} (epoch {state.epoch})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train the CarDealersPro price model.")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--amp", action="store_true", help="Enable mixed precision (CUDA only).")
    p.add_argument("--run-name", type=str, default="price_model")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(main_async(args)))