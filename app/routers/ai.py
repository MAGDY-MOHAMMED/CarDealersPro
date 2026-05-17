from fastapi import APIRouter
from app.schemas import PricePredictRequest, PricePredictResponse, ImageInspectResponse

router = APIRouter(prefix="/ai", tags=["AI"])


#
@router.post("/price-predict", response_model=PricePredictResponse)
async def predict_price(request: PricePredictRequest):
    # Placeholder: integrate trained model later
    return PricePredictResponse(predicted_price=250000.0, confidence=0.85)


#
@router.post("/inspect-image", response_model=ImageInspectResponse)
async def inspect_image(image_url: str):
    # Placeholder
    return ImageInspectResponse(damage_percentage=0.05, issues=["scratch on left door"])