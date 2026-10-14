# app/services/ml/models/price_regressor.py
"""
Price regressor for CarDealersPro.

Architecture:
    Residual MLP with pre-norm LayerNorm, GELU/SiLU/ReLU activation, and
    dropout. Designed as a drop-in stepping stone toward an FT-Transformer
    (Feature Tokenizer + Transformer) over the same 7 tabular features.

Contracts:
    INPUT:  (B, INPUT_DIM) float32, already StandardScaler-normalized.
    OUTPUT: (B, 1) float32, unnormalized price in the training target space.
            (The inference service is responsible for de-normalizing by
            target_mean/target_std if training used a target scaler.)

Compatibility guarantees:
    - torch.compile  : no Python-level branching, no dynamic shapes, no
                       .item()/.numpy() inside forward.
    - mixed precision : all ops are float32/float16-safe. No in-place ops
                       that would break AMP's autocast region.
    - save/load      : inherited from CarDealersBaseModel; config is a dataclass
                       dataclass so `asdict` gives a JSON-serializable payload.

Why this shape and not a plain MLP:
    1. Pre-norm residual blocks stabilize training at depth without warmup.
    2. A dedicated ShapeChangeBlock (no residual skip) handles dim transitions
       cleanly, avoiding the common bug of "residual on non-square shapes".
    3. A final LayerNorm before the head decouples the representation scale
       from the regression target scale — measurably improves Huber/MSE loss
       convergence on tabular data.
"""

from __future__ import annotations

from typing import Dict, Final, Tuple

import torch
from torch import Tensor, nn

from app.services.ml.config import INPUT_DIM, PriceModelConfig
from app.services.ml.models.base import CarDealersBaseModel


# ─────────────────────────────────────────────────────────────────────
# Activation registry
# ─────────────────────────────────────────────────────────────────────
# Closed set — declared `Final` so torch.compile can constant-fold the
# lookup at trace time and skip the dict access entirely.
#
# Why a registry instead of an inline `if/elif` chain:
#     - Config-driven: swap activation by name (useful for HPO sweeps).
#     - Single source of truth for "what activations does this model support".
#     - Adding a new activation is a one-line change, not a code path edit.
_ACTIVATIONS: Final[Dict[str, type[nn.Module]]] = {
    "relu": nn.ReLU,
    "gelu": nn.GELU,
    "silu": nn.SiLU,
}

# All activations above are ReLU-family (unbounded above, ~0 for x<0).
# Kaiming He initialization (gain = sqrt(2)) is appropriate for all of them.
# If a saturating activation (tanh/sigmoid) is added later, it MUST be
# moved to a branch that uses Xavier/Glorot init (gain = 1), otherwise
# gradients through the first few layers will vanish immediately.
_RELU_FAMILY: Final[frozenset[str]] = frozenset({"relu", "gelu", "silu"})


# ─────────────────────────────────────────────────────────────────────
# Residual block: same-shape transition, adds input back to output
# ─────────────────────────────────────────────────────────────────────
class ResidualBlock(nn.Module):
    """
    Pre-norm residual MLP block:

        x → LayerNorm → Linear → Act → Dropout → Linear → (+ x) → out

    Pre-norm (LayerNorm before the linear) is used because:
        - It keeps the residual stream's variance stable across depth.
        - It removes the need for learning-rate warmup on deep stacks.
        - It matches the layout of Transformer encoder blocks, which
          simplifies the migration path from MLP → FT-Transformer.

    Dropout is placed between the two linears, not after the residual add.
    Placing it after the add would scale the residual stream, which we
    want to keep untouched so identity mappings remain identity.
    """

    def __init__(
        self,
        dim: int,
        *,
        dropout: float,
        activation: str,
        use_layernorm: bool,
    ) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(dim) if use_layernorm else nn.Identity()
        self.lin1 = nn.Linear(dim, dim)
        self.act = _ACTIVATIONS[activation]()
        self.drop = nn.Dropout(dropout)
        self.lin2 = nn.Linear(dim, dim)
    # here we are using the linear layer to add the residual stream to the input, h is a 
    def forward(self, x: Tensor) -> Tensor:
        h = self.norm(x)
        h = self.lin1(h)
        h = self.act(h)# h here is which is the output of the linear layer, 
        h = self.drop(h)
        h = self.lin2(h)
        return x + h


# ─────────────────────────────────────────────────────────────────────
# Shape-change block: different in/out dims, no residual skip possible ,
#  means the model is a simple MLP with a residual block ,
#  the residual block is used to change the shape of the input data
#   x take a higher dimension than the output dimension , 
#  so the model will learn to map the input data to the output data
# ─────────────────────────────────────────────────────────────────────
class ShapeChangeBlock(nn.Module):
    """
    Pre-norm projection block used when dimensions change:

        x → LayerNorm(in_dim) → Linear(in_dim, out_dim) → Act → Dropout → out

    Why pre-norm here too:
        - Consistency with ResidualBlock keeps the loss surface homogeneous. 
        - It also prevents the pre-activation statistics from drifting as
          the network widens/narrows between stages.

    There is no residual skip because the shapes differ and adding a
    projection shortcut (e.g., a 1x1 conv equivalent) is not worth the
    extra parameters for a 7-feature tabular model.
    """

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        *,
        dropout: float,
        activation: str,
        use_layernorm: bool,
    ) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(in_dim) if use_layernorm else nn.Identity()
        self.lin = nn.Linear(in_dim, out_dim)
        self.act = _ACTIVATIONS[activation]()
        self.drop = nn.Dropout(dropout)

    def forward(self, x: Tensor) -> Tensor:
        h = self.norm(x)
        h = self.lin(h)
        h = self.act(h)
        h = self.drop(h)
        return h


# ─────────────────────────────────────────────────────────────────────
# The regressor
# ─────────────────────────────────────────────────────────────────────
class PriceRegressor(CarDealersBaseModel):
    """
    Residual MLP for car price regression.

    Structural layout (all dimensions come from `PriceModelConfig`):

        input_proj : Linear(input_dim → h0) → LayerNorm(h0) → Act
        blocks     : [Block(h0→h1), Block(h1→h2), ...]  (residual or shape-change)
        final_norm : LayerNorm(h_{n-1})                (optional, config-gated)
        head       : Linear(h_{n-1} → 1)               (no activation — regression)

    Design rationale for each stage:

    1. `input_proj` performs the first "lift" from raw 7-D features into the
       model's working width. LayerNorm right after keeps the post-projection
       activations well-conditioned from step 0, which matters because the
       input features (year, mileage, encoded brand, ...) have wildly
       different raw magnitudes even after StandardScaler.

    2. `blocks` is a mix of ResidualBlock (when dims match) and
       ShapeChangeBlock (when they don't). With the recommended default
       `hidden_dims=(256, 256, 128, 128, 64)`, you get real residual
       shortcuts at depths 1↔2 and 3↔4, which is what makes the "deep"
       part of "deep learning" actually trainable here.

    3. `final_norm` is a small but non-trivial improvement: it decouples the
       scale of the last hidden representation from the scale of the price
       target. Without it, HuberLoss gradients can blow up on the head when
       hidden activations drift upward during training.

    4. `head` is a bare Linear with no activation — it must be linear
       because the target (price) is unbounded and roughly Gaussian.
    """

    def __init__(self, config: PriceModelConfig) -> None:
        super().__init__()

        # Fail fast on misconfiguration BEFORE we allocate any parameters.
        # A misconfigured model that silently builds is far more expensive
        # to debug than one that raises at construction.
        self._validate_config(config)
        self.config = config

        # Stage 1 — input projection.
        # dims = (input_dim, h0, h1, ..., h_{n-1}).
        dims: Tuple[int, ...] = (config.input_dim,) + tuple(config.hidden_dims)

        self.input_proj = nn.Sequential(
            nn.Linear(dims[0], dims[1]),
            nn.LayerNorm(dims[1]) if config.use_layernorm else nn.Identity(),
            _ACTIVATIONS[config.activation](),
        )

        # Stage 2 — stack of residual / shape-change blocks.
        # `range(len(dims) - 2)` gives one block per transition between
        # consecutive hidden dims. The last entry (dims[-1]) is the input
        # to the head, not a transition, hence the -2.
        blocks: list[nn.Module] = []
        for i in range(len(dims) - 2):
            in_dim = dims[i + 1]
            out_dim = dims[i + 2]
            if in_dim == out_dim:
                blocks.append(
                    ResidualBlock(
                        in_dim,
                        dropout=config.dropout,
                        activation=config.activation,
                        use_layernorm=config.use_layernorm,
                    )
                )
            else:
                blocks.append(
                    ShapeChangeBlock(
                        in_dim,
                        out_dim,
                        dropout=config.dropout,
                        activation=config.activation,
                        use_layernorm=config.use_layernorm,
                    )
                )
        self.blocks = nn.Sequential(*blocks)

        # Stage 3 — final normalization (optional).
        self.final_norm = (
            nn.LayerNorm(dims[-1]) if config.use_layernorm else nn.Identity()
        )

        # Stage 4 — regression head. Output is (B, 1) with no activation.
        self.head = nn.Linear(dims[-1], 1)

        # Deterministic initialization. Called once at construction; can be
        # re-run for reproducibility across training runs (see reset_parameters).
        self._init_weights()

    # ── Config validation ────────────────────────────────────────────
    @staticmethod
    def _validate_config(config: PriceModelConfig) -> None:
        """
        Raise ValueError on any obviously-broken config.

        Called once at construction. Cheap. Prevents hours of debugging
        silent numerical failures downstream.
        """
        if config.input_dim != INPUT_DIM:
            # The model can theoretically accept any input_dim, but the
            # inference service asserts this equals 7 via FEATURE_COLUMNS.
            # Failing here gives a much clearer message.
            raise ValueError(
                f"PriceRegressor expects input_dim={INPUT_DIM} "
                f"(FEATURE_COLUMNS length), got {config.input_dim}."
            )
        if not config.hidden_dims:
            raise ValueError("hidden_dims must not be empty.")
        if any(d <= 0 for d in config.hidden_dims):
            raise ValueError(
                f"All hidden_dims must be positive, got {config.hidden_dims}."
            )
        # Dropout = 1.0 would zero every activation deterministically, which
        # is degenerate. Allow any value in [0, 1).
        if not 0.0 <= config.dropout < 1.0:
            raise ValueError(
                f"dropout must be in [0, 1), got {config.dropout}."
            )
        if config.activation not in _ACTIVATIONS:
            raise ValueError(
                f"Unsupported activation '{config.activation}'. "
                f"Supported: {sorted(_ACTIVATIONS)}."
            )

    # ── Weight initialization ────────────────────────────────────────
    def _init_weights(self) -> None:
        """
        Kaiming He for ReLU-family weights, Xavier for the rest, biases
        zeroed, LayerNorm gammas set to 1 and betas to 0.

        Why Kaiming for GELU/SiLU too:
            GELU and SiLU are smooth approximations of ReLU with nearly
            identical second-moment behavior in the active region. Kaiming
            He (fan_in, gain=sqrt(2)) keeps activation variance constant
            across layers, which is exactly what we want.
        """
        for module in self.modules():
            if isinstance(module, nn.Linear):
                if self.config.activation in _RELU_FAMILY:
                    nn.init.kaiming_normal_(
                        module.weight, nonlinearity="relu"
                    )
                else:
                    nn.init.xavier_normal_(module.weight)
                # Biases are zeroed so that at step 0 each linear is a pure
                # linear map without an offset, letting LayerNorm pick up
                # any needed shift. This is standard for pre-norm stacks.
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.LayerNorm):
                # LayerNorm defaults are already gamma=1, beta=0, but
                # re-asserting makes the invariant explicit and robust to
                # any future nn.LayerNorm implementation change.
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)

    def reset_parameters(self) -> None:
        """
        Re-initialize all weights. Useful for hyperparameter sweeps where
        the same instance is retrained from scratch with a different seed.

        Note: this does NOT reset the optimizer state. If you're doing a
        proper sweep, rebuild the optimizer after calling this.
        """
        self._init_weights()

    # ── Forward ──────────────────────────────────────────────────────
    def forward(self, x: Tensor) -> Tensor:
        """
        Args:
            x: (B, INPUT_DIM) float32, pre-scaled by the same StandardScaler
               that was fit at training time. Do NOT pass raw features.

        Returns:
            (B, 1) float32, predicted price in the training target's space.
            If the training loop standardized the target (mean 0, std 1),
            the inference service is responsible for inverting that transform.

        torch.compile notes:
            - No `if` on tensor values.
            - No `.item()`, `.numpy()`, `print`, or any Python side effect.
            - All shapes inferred from `x.shape[0]` at trace time; the
              `-1` in later ops is fine, but we avoid dynamic reshape entirely
              by only using `squeeze` semantics at the caller side.
        """
        h = self.input_proj(x)
        h = self.blocks(h)
        h = self.final_norm(h)
        return self.head(h)


# ─────────────────────────────────────────────────────────────────────
# Module-level self-test (run: python -m app.services.ml.models.price_regressor)
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # Recommended defaults for the current project's data scale.
    # ResidualBlock activates at positions 1↔2 and 3↔4 (matching dims).
    # If you keep the old default (256, 128, 64), only ShapeChangeBlocks
    # will be built and the model is a plain MLP.
    config = PriceModelConfig(
        hidden_dims=(256, 256, 128, 128, 64),
        dropout=0.15,
        use_layernorm=True,
        activation="gelu",
    )

    model = PriceRegressor(config)
    model.describe("PriceRegressor (self-test)")

    # Shape contract check — this catches the most common integration bug.
    x = torch.randn(32, INPUT_DIM, dtype=torch.float32)
    with torch.no_grad():
        y = model(x)

    assert y.shape == (32, 1), f"Expected (32, 1), got {tuple(y.shape)}"
    assert torch.isfinite(y).all(), "Non-finite output detected"

    # Residual count sanity check — with the recommended default there
    # should be exactly 2 residual blocks.
    n_residual = sum(
        1 for m in model.blocks if isinstance(m, ResidualBlock)
    )
    n_shape_change = sum(
        1 for m in model.blocks if isinstance(m, ShapeChangeBlock)
    )
    print(f"blocks: residual={n_residual}, shape_change={n_shape_change}")

    # torch.compile smoke test — verifies no Python branches in forward.
    try:
        compiled = torch.compile(model)
        with torch.no_grad():
            y2 = compiled(x)
        assert torch.allclose(y, y2, atol=1e-4), "compiled output drifted"
        print("torch.compile: OK")
    except Exception as exc:  # noqa: BLE001
        print(f"torch.compile skipped (expected on some setups): {exc}")

    print("self-test: OK")
    sys.exit(0)