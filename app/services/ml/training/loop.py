"""
Reusable Trainer for CarDealersPro models.

Handles:
    - AMP (mixed precision) when CUDA.
    - Gradient clipping.
    - LR scheduler (cosine or plateau).
    - Callback dispatch.
    - Consistent logging via app logger + request_id.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import torch
import torch.nn as nn
from torch import Tensor
from torch.optim import AdamW
from typing import TYPE_CHECKING

from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau

if TYPE_CHECKING:
    # Only imported for type checkers; never at runtime.
    # The concrete class was renamed _LRScheduler -> LRScheduler across
    # PyTorch versions, so importing it eagerly is fragile.
    from torch.optim.lr_scheduler import LRScheduler  # noqa: F401 
from torch.utils.data import DataLoader

from app.core.logging_config import logger
from app.core.request_id import get_request_id
from app.services.ml.config import MODELS_DIR, TrainingConfig
from app.services.ml.training.callbacks import Callback


# ─────────────────────────────────────────────────────────────────────
# Mutable training state (kept separate from the trainer for clarity)
# ─────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class TrainState:
    epoch: int = 0
    global_step: int = 0
    train_loss: float = 0.0
    val_loss: float = 0.0
    best_val_loss: float = float("inf")


# ─────────────────────────────────────────────────────────────────────
# Trainer
# ─────────────────────────────────────────────────────────────────────
class Trainer:
    """
    Single-model trainer. Not distributed. Not DataParallel.
    Assumes model + loaders already on the correct device.
    """

    def __init__(
        self,
        *,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        criterion: nn.Module,
        cfg: TrainingConfig,
        device: torch.device,
        run_name: str,
        callbacks: Optional[Iterable[Callback]] = None,
    ) -> None:
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.criterion = criterion
        self.cfg = cfg
        self.device = device
        self.run_name = run_name
        self.callbacks: list[Callback] = list(callbacks or [])
        self.state = TrainState()

        self.optimizer = AdamW(
            model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay
        )
        self.scheduler: Optional["LRScheduler"] = self._build_scheduler()

        # AMP only meaningful on CUDA. Guarded so CPU runs still work.
        # AMP only meaningful on CUDA. Guarded so CPU runs still work.
        self.use_amp = cfg.amp and device.type == "cuda"
        # PyTorch 2.4+ recommended API. Old form torch.cuda.amp.GradScaler
        # emits a DeprecationWarning and will be removed.
        self.scaler = torch.amp.GradScaler(
            device=self.device.type,
            enabled=self.use_amp,
        )

    # ── Scheduler factory ───────────────────────────────────────────
    def _build_scheduler(self) -> Optional["LRScheduler"]:
        if self.cfg.scheduler == "cosine":
            return CosineAnnealingLR(self.optimizer, T_max=self.cfg.epochs)
        if self.cfg.scheduler == "plateau":
            return ReduceLROnPlateau(self.optimizer, mode="min", factor=0.5, patience=3)
        return None

    # ── One train epoch ─────────────────────────────────────────────
    def _train_epoch(self) -> float:
        self.model.train()
        running = 0.0
        n_batches = 0

        for xb, yb in self.train_loader:
            xb = xb.to(self.device, non_blocking=True)
            yb = yb.to(self.device, non_blocking=True)

            self.optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast(
                device_type=self.device.type,
                enabled=self.use_amp,
                dtype=torch.float16,
            ):
                logits = self.model(xb)
                loss = self.criterion(logits, yb)

            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.grad_clip_norm)
            self.scaler.step(self.optimizer)
            self.scaler.update()

            running += loss.item()
            n_batches += 1
            self.state.global_step += 1

            if self.state.global_step % self.cfg.log_every_n_steps == 0:
                logger.debug(
                    "ML train: step",
                    extra={
                        "request_id": get_request_id(),
                        "step": self.state.global_step,
                        "loss": float(loss.item()),
                    },
                )

        return running / max(n_batches, 1)

    # ── One val epoch ───────────────────────────────────────────────
    @torch.no_grad()
    def _val_epoch(self) -> float:
        self.model.eval()
        running = 0.0
        n_batches = 0

        for xb, yb in self.val_loader:
            xb = xb.to(self.device, non_blocking=True)
            yb = yb.to(self.device, non_blocking=True)

            with torch.amp.autocast(
                device_type=self.device.type,
                enabled=self.use_amp,
                dtype=torch.float16,
            ):
                logits = self.model(xb)
                loss = self.criterion(logits, yb)

            running += loss.item()
            n_batches += 1

        return running / max(n_batches, 1)

    # ── Public API ──────────────────────────────────────────────────
    def fit(self) -> TrainState:
        logger.info(
            "ML training: started",
            extra={
                "request_id": get_request_id(),
                "run_name": self.run_name,
                "epochs": self.cfg.epochs,
                "device": str(self.device),
                "use_amp": self.use_amp,
            },
        )

        for cb in self.callbacks:
            cb.on_train_begin(self)

        t0 = time.perf_counter()
        for epoch in range(1, self.cfg.epochs + 1):
            self.state.epoch = epoch
            self.state.train_loss = self._train_epoch()
            self.state.val_loss = self._val_epoch()

            if isinstance(self.scheduler, ReduceLROnPlateau):
                self.scheduler.step(self.state.val_loss)
            elif self.scheduler is not None:
                self.scheduler.step()

            logger.info(
                "ML training: epoch",
                extra={
                    "request_id": get_request_id(),
                    "epoch": epoch,
                    "train_loss": round(self.state.train_loss, 6),
                    "val_loss": round(self.state.val_loss, 6),
                    "lr": float(self.optimizer.param_groups[0]["lr"]),
                },
            )

            for cb in self.callbacks:
                cb.on_epoch_end(self)
            if any(cb.should_stop() for cb in self.callbacks):
                break

        for cb in self.callbacks:
            cb.on_train_end(self)

        logger.info(
            "ML training: finished",
            extra={
                "request_id": get_request_id(),
                "run_name": self.run_name,
                "duration_seconds": round(time.perf_counter() - t0, 2),
                "best_val_loss": round(self.state.best_val_loss, 6),
            },
        )
        return self.state

    # ── Checkpointing (called by EarlyStopping) ─────────────────────
    def save_checkpoint(self, filename: str) -> None:
        self.state.best_val_loss = min(self.state.best_val_loss, self.state.val_loss)
        path = MODELS_DIR / f"{self.run_name}_{filename}"
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "epoch": self.state.epoch,
                "val_loss": self.state.val_loss,
            },
            path,
        )
        logger.info(
            "ML training: checkpoint saved",
            extra={
                "request_id": get_request_id(),
                "path": str(path),
                "val_loss": round(self.state.val_loss, 6),
            },
        )