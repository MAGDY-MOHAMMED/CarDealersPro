import torch
from torch import nn
from app.services.ml.models.price_regressor import PriceRegressor
from app.services.ml.data_pipeline import StandardScalerBundle
from app.services.ml.config import ARTIFACTS_DIR, PriceModelConfig

class PriceInferenceService:
    def __init__(self):
        self.scaler = StandardScalerBundle.load(ARTIFACTS_DIR / "price_scaler.pt")
        self.model = PriceRegressor.load(
            ARTIFACTS_DIR / "price_model.pt",
            config_cls=PriceModelConfig,
        )
        self.model.eval()

    def predict(self, request):
        features = torch.tensor([[
            request.year, request.mileage,
            request.brand_enc, request.model_enc,
            request.fuel_type_enc, request.transmission_enc,
            request.body_type_enc,
        ]], dtype=torch.float32)
        scaled = self.scaler.transform_features(features)
        with torch.no_grad():
            pred_scaled = self.model(scaled)
            pred_real = self.scaler.inverse_transform_targets(pred_scaled)
        return {"predicted_price": float(pred_real.item()), "confidence": 0.85}

class DamageInferenceService:
    """Thin adapter around DamagePipeline."""

    def __init__(self) -> None:
        from app.services.ml.damage_pipeline import get_damage_pipeline
        self._pipeline = get_damage_pipeline()

    def inspect(self, image_bytes: bytes) -> dict:
        result = self._pipeline.predict(image_bytes)
        # Only surface fields the HTTP schema knows about.
        return {
            "damage_percentage": result["damage_percentage"],
            "issues": result["issues"] or [result["damage_type"]],
        }