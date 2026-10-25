"""
Damage detection pipeline for CarDealersPro.

Model contract (planned):
    Input : RGB image, resized to 224x224, ImageNet-normalized.
    Output: (N, num_classes) logits.
            Index 0    -> "no_damage"
            Index 1..N -> damage types in DAMAGE_CLASSES order.

Status:
    The pipeline scaffolding is fully implemented, but the trained weights
    do NOT exist yet. Until they are trained and saved to
    `ARTIFACTS_DIR / "damage_model.pt"`, `DamagePipeline.load()` raises
    FileNotFoundError with a clear message.

    To train:
        1. Collect labeled car images (each image -> a single damage class).
        2. Build a torchvision ImageFolder dataset.
        3. Train `DamageCNN` defined below.
        4. Save the state_dict via torch.save(model.state_dict(), ...).
           The class order must match DAMAGE_CLASSES below.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch
from torch import Tensor, nn
from torchvision import models

from app.core.logging_config import logger
from app.core.request_id import get_request_id
from app.services.ml.config import ARTIFACTS_DIR, DamageModelConfig


# --------------------------------------------------------------------------- #
# Class labels — MUST match the training order exactly.
# --------------------------------------------------------------------------- #
DAMAGE_CLASSES: tuple[str, ...] = (
    "no_damage",
    "scratch",
    "dent",
    "broken_glass",
)

# ImageNet normalization (matches torchvision pretrained weights).
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)
_INPUT_SIZE = 224


# --------------------------------------------------------------------------- #
# Model definition
# --------------------------------------------------------------------------- #
class DamageCNN(nn.Module):
    """
    ResNet18 backbone + classification head.

    If `config.freeze_backbone` is True, only the head is trainable
    (fast, works with small datasets). If False, the full network is
    fine-tuned (needs more data + lower LR).
    """

    def __init__(self, config: DamageModelConfig) -> None:
        super().__init__()
        if config.backbone != "resnet18":
            raise ValueError(
                f"Unsupported backbone '{config.backbone}'. "
                f"Only 'resnet18' is wired up today."
            )

        weights = models.ResNet18_Weights.DEFAULT if config.pretrained else None
        self.backbone = models.resnet18(weights=weights)

        if config.freeze_backbone:
            for p in self.backbone.parameters():
                p.requires_grad = False

        in_features = self.backbone.fc.in_features
        head: list[nn.Module] = [nn.Dropout(config.dropout)]
        if config.head_hidden:
            head += [
                nn.Linear(in_features, config.head_hidden),
                nn.ReLU(inplace=True),
                nn.Dropout(config.dropout),
                nn.Linear(config.head_hidden, config.num_classes),
            ]
        else:
            head.append(nn.Linear(in_features, config.num_classes))
        self.backbone.fc = nn.Sequential(*head)

    def forward(self, x: Tensor) -> Tensor:
        return self.backbone(x)


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
class DamagePipeline:
    """
    End-to-end damage inference:

        bytes -> PIL -> tensor -> model -> (damage_percentage, issues)

    Responsibilities:
        - Load and cache the trained weights.
        - Preprocess images.
        - Translate model logits to a human-friendly response.
    """

    def __init__(
        self,
        config: Optional[DamageModelConfig] = None,
        weights_path: Optional[Path] = None,
        device: str | torch.device = "cpu",
    ) -> None:
        self.config = config or DamageModelConfig()
        self.weights_path = weights_path or (ARTIFACTS_DIR / "damage_model.pt")
        self.device = torch.device(device)
        self.model: Optional[DamageCNN] = None

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        """Load the model on demand. Raises FileNotFoundError if weights missing."""
        if self.model is not None:
            return

        if not self.weights_path.exists():
            raise FileNotFoundError(
                f"Damage model weights not found at {self.weights_path}. "
                f"Train one and save it as `damage_model.pt` under "
                f"{ARTIFACTS_DIR}."
            )

        model = DamageCNN(self.config)
        try:
            state = torch.load(
                self.weights_path,
                map_location=self.device,
                weights_only=True,
            )
        except TypeError:
            # PyTorch < 2.4 has no `weights_only`.
            state = torch.load(self.weights_path, map_location=self.device)

        # Allow both raw state_dict and dicts with a "state_dict" wrapper.
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        model.load_state_dict(state)
        model.to(self.device)
        model.eval()
        self.model = model

        logger.info(
            "DamagePipeline: loaded",
            extra={
                "request_id": get_request_id(),
                "weights_path": str(self.weights_path),
                "device": str(self.device),
            },
        )

    # ------------------------------------------------------------------ #
    # Preprocessing
    # ------------------------------------------------------------------ #
    def preprocess(self, image_bytes: bytes) -> Tensor:
        """
        bytes -> normalized (1, 3, 224, 224) float32 tensor on self.device.

        Imported lazily so that this module stays importable in environments
        without Pillow (e.g. minimal ML tooling).
        """
        from io import BytesIO

        from PIL import Image
        from torchvision import transforms

        transform = transforms.Compose(
            [
                transforms.Resize((_INPUT_SIZE, _INPUT_SIZE)),
                transforms.ToTensor(),
                transforms.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
            ]
        )

        try:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Could not decode image: {exc}") from exc

        tensor = transform(img).unsqueeze(0).to(self.device)
        return tensor

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    @torch.no_grad()
    def predict(self, image_bytes: bytes) -> dict:
        """
        Returns:
            {
                "damage_percentage": float,   # 0..100
                "damage_type": str,           # top-1 damage class
                "issues": list[str],          # all non-"no_damage" classes above threshold
                "confidence": float,          # softmax probability of top-1
            }
        """
        self.load()
        assert self.model is not None  # for type-checkers

        x = self.preprocess(image_bytes)
        logits = self.model(x)                       # (1, num_classes)
        probs = torch.softmax(logits, dim=-1)[0]     # (num_classes,)

        # "damage_percentage" = 100 * P(any damage class).
        p_no_damage = float(probs[0].item())
        damage_percentage = round((1.0 - p_no_damage) * 100.0, 2)

        # "issues" = all damage classes with probability >= 15%.
        threshold = 0.15
        issues = [
            DAMAGE_CLASSES[i]
            for i in range(1, len(DAMAGE_CLASSES))
            if float(probs[i].item()) >= threshold
        ]

        top_idx = int(torch.argmax(probs).item())
        top_class = DAMAGE_CLASSES[top_idx]
        confidence = round(float(probs[top_idx].item()), 4)

        logger.info(
            "DamagePipeline: inference done",
            extra={
                "request_id": get_request_id(),
                "damage_percentage": damage_percentage,
                "top_class": top_class,
                "confidence": confidence,
            },
        )

        return {
            "damage_percentage": damage_percentage,
            "damage_type": top_class,
            "issues": issues,
            "confidence": confidence,
        }


# --------------------------------------------------------------------------- #
# Module-level singleton (matches the pattern in training/inference.py)
# --------------------------------------------------------------------------- #
_pipeline: Optional[DamagePipeline] = None


def get_damage_pipeline() -> DamagePipeline:
    """Lazy singleton accessor."""
    global _pipeline
    if _pipeline is None:
        _pipeline = DamagePipeline()
    return _pipeline


# --------------------------------------------------------------------------- #
# Self-test (run: python -m app.services.ml.damage_pipeline)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print("Damage classes:", DAMAGE_CLASSES)
    cfg = DamageModelConfig()
    model = DamageCNN(cfg)
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"DamageCNN params: total={total:,}, trainable={trainable:,}")

    # Forward smoke test with random input.
    x = torch.randn(2, 3, _INPUT_SIZE, _INPUT_SIZE)
    with torch.no_grad():
        y = model(x)
    print("Forward output shape:", tuple(y.shape))
    assert y.shape == (2, cfg.num_classes)
    print("damage_pipeline self-test: OK")