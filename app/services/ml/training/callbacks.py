"""
Training callbacks for CarDealersPro.

Contract:
    Each callback may implement any subset of:
        on_train_begin(trainer) -> None
        on_epoch_end(trainer)   -> None
        on_train_end(trainer)   -> None
        should_stop()           -> bool

    `Trainer.fit` calls these hooks. `should_stop` is checked after every
    epoch; if ANY callback returns True, training halts.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless backend — no GUI required on servers
import matplotlib.pyplot as plt

from app.core.logging_config import logger
from app.core.request_id import get_request_id
from app.services.ml.config import ARTIFACTS_DIR


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class Callback(ABC):
    """Base callback. Default no-ops keep subclasses small."""

    def on_train_begin(self, trainer: Any) -> None: ...
    def on_epoch_end(self, trainer: Any) -> None: ...
    def on_train_end(self, trainer: Any) -> None: ...

    def should_stop(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# EarlyStopping
# ---------------------------------------------------------------------------
class EarlyStopping(Callback):
    """
    Stop training when `val_loss` stops improving for `patience` epochs.

    Also saves the best checkpoint by calling
    `trainer.save_checkpoint(checkpoint_name)` — so there is exactly ONE
    place that owns "best model" state (this callback).
    """

    def __init__(
        self,
        patience: int,
        min_delta: float = 0.0,
        checkpoint_name: str = "best.pt",
    ) -> None:
        if patience < 1:
            raise ValueError(f"patience must be >= 1, got {patience}")
        self.patience = patience
        self.min_delta = min_delta
        self.checkpoint_name = checkpoint_name

        self.best: float = float("inf")
        self.counter: int = 0
        self.best_epoch: int = 0
        self._stop: bool = False

    # -- hook called by Trainer after each epoch --
    def on_epoch_end(self, trainer: Any) -> None:
        current = float(trainer.state.val_loss)

        if current < self.best - self.min_delta:
            # Improvement → reset patience, save checkpoint.
            self.best = current
            self.counter = 0
            self.best_epoch = trainer.state.epoch
            trainer.state.best_val_loss = current
            trainer.save_checkpoint(self.checkpoint_name)
            logger.info(
                "ML training: val_loss improved",
                extra={
                    "request_id": get_request_id(),
                    "epoch": trainer.state.epoch,
                    "val_loss": round(current, 6),
                },
            )
            return

        # No improvement → count up, maybe stop.
        self.counter += 1
        logger.info(
            "ML training: no improvement",
            extra={
                "request_id": get_request_id(),
                "epoch": trainer.state.epoch,
                "counter": self.counter,
                "patience": self.patience,
                "best_val_loss": round(self.best, 6),
            },
        )
        if self.counter >= self.patience:
            self._stop = True
            logger.info(
                "ML training: early stop triggered",
                extra={
                    "request_id": get_request_id(),
                    "best_val_loss": round(self.best, 6),
                    "best_epoch": self.best_epoch,
                    "stopped_at_epoch": trainer.state.epoch,
                },
            )

    def should_stop(self) -> bool:
        return self._stop


# ---------------------------------------------------------------------------
# LossCurveCallback
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LossCurveCallback(Callback):
    """Persist train/val loss curves as a PNG after training ends."""

    run_name: str
    history: dict[str, list[float]] = field(
        default_factory=lambda: {"train": [], "val": []}
    )

    def on_epoch_end(self, trainer: Any) -> None:
        self.history["train"].append(float(trainer.state.train_loss))
        self.history["val"].append(float(trainer.state.val_loss))

    def on_train_end(self, trainer: Any) -> None:
        if not self.history["train"]:
            return  # Nothing to plot

        fig, ax = plt.subplots(figsize=(8, 5))
        epochs = range(1, len(self.history["train"]) + 1)
        ax.plot(epochs, self.history["train"], label="train", linewidth=2)
        ax.plot(epochs, self.history["val"], label="val", linewidth=2)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Loss")
        ax.set_title(f"Loss curve — {self.run_name}")
        ax.grid(alpha=0.3)
        ax.legend()
        out = ARTIFACTS_DIR / f"{self.run_name}_loss.png"
        fig.tight_layout()
        fig.savefig(out, dpi=120)
        plt.close(fig)
        logger.info(
            "ML training: loss curve saved",
            extra={"request_id": get_request_id(), "path": str(out)},
        )