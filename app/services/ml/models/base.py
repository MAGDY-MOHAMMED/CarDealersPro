"""
Base class for all CarDealersPro ML models. 
here i define the base class for all models 
Provides:
    - Consistent dtype/device handling for inputs.
    - `count_parameters` utility for logging.
    - Uniform `save`/`load` via state_dict + config serialization.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass
from pathlib import Path
import json
from typing import Any, Dict, Protocol

import torch
from torch import Tensor, nn

from app.core.logging_config import logger
from app.core.request_id import get_request_id

# Protocol is a way to define a contract for a class , it is like an interface in other languages
class SerializableConfig(Protocol):
    def __dict__(self) -> dict: ...


class CarDealersBaseModel(nn.Module, ABC):
    """
    Abstract base for models used in the CarDealersPro platform.

    Subclasses MUST:
        - Define `forward(self, x: Tensor) -> Tensor`.
        - Expose a `config` attribute (a dataclass instance) for serialization. 
        - The model config will be saved in a json file , and the model weights will be saved in a pth file.
        then we can load the model using the config file and the pth file. 
        we can attach the config with pth  by using the `load` method. 
        load method should be implemented in the subclass in order to load the model from the config file and the pth file.
    """
    # the config attribute is set by the subclass,
    #  subclass here is the model class ,
    # model class here is the class that inherits from this base class the base class is CarDealersBaseModel
    # CarDealersBaseModel is the base class for all models for predict the car price, taking its data from the database
    # and saving the config and weights in separate files
    config: Any  # set by subclass

    # init method is used to initialize the model , it calls the parent class constructor how ? 
    def __init__(self) -> None:
        super().__init__()  # in detail means nn.Module.__init__(self)

    def count_parameters(self, *, trainable_only: bool = True) -> int:
        """Count parameters. ~free (no forward pass).  
        that means no need to pass any data to count parameters
        why ? because we are counting the parameters of the model, not the parameters of the data 
        and the parameters of the model are fixed and not dependent on the data
        that's why we can count them without passing any data
        and no forward pass In detail means we are not passing any data through the model to count the parameters
        we are just counting the parameters of the model 
        and if we pass data through the model, it will be a forward pass and it will be slow
        so we will leave the forward pass to the model itself """
        params = self.parameters()
        if trainable_only:
            return sum(p.numel() for p in params if p.requires_grad)  # numel() returns the number of elements in the tensor
            # why requires_grad? because we only want to count the trainable parameters not the non-trainable parameters
        return sum(p.numel() for p in params)

    def describe(self, name: str) -> None:
        """Log a one-shot summary of the model."""

        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.parameters())
        logger.info(
            f"ML model: {name}",  
            extra={
                "request_id": get_request_id(),
                "trainable_params": self.count_parameters(trainable_only=True), # only the head 
                "total_params": self.count_parameters(trainable_only=False),
                # why trainable_only=False? because we want to count all parameters not just trainable parameters why ? 
                # because we want to know the total number of parameters in the model 
            },
        )

    # abstractmethod here because we want to make sure that the subclass ( which is the model ) implements the forward method , means
    @abstractmethod
    def forward(self, x: Tensor) -> Tensor:
        """Subclasses implement this."""
        raise NotImplementedError

    def save(self, path: Path) -> None:
        """Persist config + weights. `.pt` file is self-describing."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # 1. استخرج الـ config كـ dictionary (بيشتغل مع tuple و dataclass)
        config_dict = asdict(self.config) if is_dataclass(self.config) else self.config

        payload: Dict[str, Any] = {
            # why asdict? because we want to convert the dataclass ( coming from config  that model was trained with and make the file a json file after learning so we can make the json file a readable file , 
            # so the flow is dataclass -> json file -> readable file , 
            # why not data class to readable file directly? because dataclass is not readable by humans , it is readable by machines
            #  ( if it is a dataclass , which is the case for most models )
            # why hasattr? because we want to check if the config is a dataclass or not 
            # why "__dataclass_fields__" ? because we want to check if the config is a dataclass or not , 
            # if it is a dataclass we convert it to a dictionary using asdict and if it is not a dataclass we use it as it is , how ? 
            "config": config_dict,
            "state_dict": self.state_dict(),
            "class_name": type(self).__name__,  # why type(self).__name__? because we want to know the name of the class
            "format_version": 1,  # ← for future versioning support
        }
        torch.save(payload, path)  # why save with torch.save? because we want to save the model in a way that it can be loaded later in any environment

        # 3. hybrid approach: save config as json for human readability
        json_path = path.with_suffix(".json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "class_name": type(self).__name__,
                        "config": _to_json_safe(config_dict),
                    },
                    f,
                    indent=2,           # ← beautiful format
                    ensure_ascii=False, # ← save arabic characters
                )
        except Exception as e:
            logger.warning(f"Failed to write JSON sidecar: {e}", extra={"request_id": get_request_id()})
            # we won't fail the save if the JSON sidecar fails

        logger.info(
            "ML model: saved",
            extra={"request_id": get_request_id(), "path": str(path)},
        )

    # here i need to load the model from the path 
    # why torch.load? because we saved the model using torch.save
    # why map_location="cpu"? because we want to load the model on cpu 
    @classmethod
    def load(
        cls,
        path: Path,
        config_cls: type,           # ← تمرر الـ dataclass class (مثلاً PriceModelConfig)
        *,
        map_location: str = "cpu",  # ← الافتراضي CPU
        device: str | torch.device | None = None,  # ← لو عايز ينقل لجهاز معين بعد التحميل
        eval_mode: bool = True,     # ← يسيب الموديل في وضع التقييم
        weights_only: bool = True,  # ← للأمان (PyTorch 2.4+)
    ) -> "CarDealersBaseModel":
        try:
            payload = torch.load(path, map_location=map_location, weights_only=weights_only)
        except TypeError:
            # PyTorch أقدم من 2.4 → مفيش weights_only
            payload = torch.load(path, map_location=map_location)
            # log the error
            logger.error(
                f"PyTorch version is older than 2.4, weights_only parameter is not supported.",
                extra={"request_id": get_request_id()},
            )
            # continue with the loading , but without weights_only

        if "config" not in payload or "state_dict" not in payload:
            logger.error(
                f"Invalid checkpoint at {path}. "
                f"Expected keys: 'config', 'state_dict'. "
                f"Got: {list(payload.keys())}",
                extra={"request_id": get_request_id()},
            )
            raise ValueError(
                f"Invalid checkpoint at {path}. "
                f"Expected keys: 'config', 'state_dict'. "
                f"Got: {list(payload.keys())}"
            )

        config = config_cls(**payload["config"])
        model = cls(config)
        model.load_state_dict(payload["state_dict"])  # the state dict is the model weights

        # 5. انقل للجهاز المطلوب (لو محدد)
        #    لو مش محدد → يفضل على CPU
        target_device = torch.device(device) if device else torch.device(map_location)
        model = model.to(target_device)

        # 6. وضع التقييم (بيوقف dropout و batchnorm updates)
        if eval_mode:
            model.eval()

        logger.info(
            "ML model: loaded",
            extra={
                "request_id": get_request_id(),
                "path": str(path),
                "device": str(target_device),
                "class_name": payload.get("class_name"),
                "format_version": payload.get("format_version"),
            },
        )
        return model


def _to_json_safe(obj: Any) -> Any:
    """محول recursive لتحويل أي object لشكل JSON-compatible."""
    if isinstance(obj, tuple):  # convert tuple to list
        return list(obj)
    if isinstance(obj, Path):  # convert Path to string
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):  # convert dataclass to dict
        return _to_json_safe(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}  # convert dict to json safe
    if isinstance(obj, (list, set)):
        return [_to_json_safe(v) for v in obj]  # convert list to json safe
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return str(obj)  # fallback [احتياطي] لأي نوع تاني





if __name__ == "__main__":
    import tempfile
    from dataclasses import dataclass
    from typing import Tuple

    # ---- Dummy config + model للاختبار ----
    @dataclass(frozen=True)
    class _TestConfig:
        input_dim: int = 4
        hidden_dims: Tuple[int, ...] = (16, 8)

    class _TestModel(CarDealersBaseModel):
        def __init__(self, config: _TestConfig):
            super().__init__()
            self.config = config
            self.net = nn.Sequential(
                nn.Linear(config.input_dim, config.hidden_dims[0]),
                nn.ReLU(),
                nn.Linear(config.hidden_dims[0], config.hidden_dims[1]),
                nn.ReLU(),
                nn.Linear(config.hidden_dims[1], 1),
            )

        def forward(self, x: Tensor) -> Tensor:
            return self.net(x)

    # ---- Test 1: إنشاء + describe + count ----
    model = _TestModel(_TestConfig()) # means create a new model with the test config , _ means private for internal use
    model.describe("_TestModel") # means print the model description
    total = model.count_parameters(trainable_only=False)# means count all parameters
    trainable = model.count_parameters(trainable_only=True)# means count trainable parameters
    assert total > 0 and trainable > 0 and trainable <= total
    print(f" count_parameters: total={total}, trainable={trainable}")

    # ---- Test 2: forward pass ----
    x = torch.randn(2, 4)
    y = model(x)
    assert y.shape == (2, 1), f"Expected (2,1), got {y.shape}"
    print(f" forward pass: {tuple(x.shape)} -> {tuple(y.shape)}")

    # ---- Test 3: save + JSON sidecar ----
    with tempfile.TemporaryDirectory() as tmp:
        ckpt = Path(tmp) / "test_model.pt"
        model.save(ckpt)
        assert ckpt.exists(), "checkpoint not created"
        assert ckpt.with_suffix(".json").exists(), "JSON sidecar not created"
        print(f" save: {ckpt.name} + {ckpt.with_suffix('.json').name}")

        # ---- Test 4: load + state_dict equality ----
        loaded = _TestModel.load(ckpt, config_cls=_TestConfig)
        assert loaded.config == model.config, "config mismatch"
        assert not loaded.training, "should be in eval mode"
        for k in model.state_dict():
            assert torch.equal(model.state_dict()[k], loaded.state_dict()[k]), f"mismatch in {k}" # means check if the tensors are equal ,tensors that carry the model parameters
        print(" load: state_dict matches, eval mode, config preserved")

        # ---- Test 5: forward after load ----
        y2 = loaded(x)
        assert y2.shape == (2, 1)
        print(" forward after load works")

    # ---- Test 6: _to_json_safe ----
    safe = _to_json_safe({"t": (1, 2), "p": Path("a/b"), "n": {"x": (3, 4)}})
    assert safe["t"] == [1, 2] and isinstance(safe["p"], str) and safe["n"]["x"] == [3, 4]
    print(" _to_json_safe handles tuple/Path/nested")

    print(" base.py is fully working.")