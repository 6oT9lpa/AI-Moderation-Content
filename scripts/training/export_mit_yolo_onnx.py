"""Export a pinned MultimediaTechLab YOLO checkpoint to the runtime matrix contract."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch
from torch import Tensor, nn

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.training.train_mit_yolo import verify_checkout


class MitYoloExportAdapter(nn.Module):
    """Decode the main YOLO head into ``xywh + class probabilities`` rows."""

    def __init__(self, model: nn.Module, anchor_grid: Tensor, scaler: Tensor) -> None:
        super().__init__()
        self.model = model
        self.register_buffer("anchor_grid", anchor_grid)
        self.register_buffer("scaler", scaler)

    def forward(self, images: Tensor) -> Tensor:
        predictions = self.model(images)["Main"]
        class_logits: list[Tensor] = []
        box_distances: list[Tensor] = []
        for class_head, _anchor_head, box_head in predictions:
            class_logits.append(class_head.permute(0, 2, 3, 1).flatten(1, 2))
            box_distances.append(box_head.permute(0, 2, 3, 1).flatten(1, 2))
        classes = torch.cat(class_logits, dim=1).sigmoid()
        distances = torch.cat(box_distances, dim=1) * self.scaler.view(1, -1, 1)
        left_top, right_bottom = distances.chunk(2, dim=-1)
        xyxy = torch.cat((self.anchor_grid - left_top, self.anchor_grid + right_bottom), dim=-1)
        center = (xyxy[..., :2] + xyxy[..., 2:]) / 2
        size = xyxy[..., 2:] - xyxy[..., :2]
        return torch.cat((center, size, classes), dim=-1)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--training-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    verify_checkout(checkout)
    for required in (args.training_config, args.checkpoint):
        if not required.is_file():
            raise FileNotFoundError(required)

    sys.path.insert(0, str(checkout))
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    from omegaconf import OmegaConf
    from yolo.model.yolo import create_model
    from yolo.utils.bounding_box_utils import create_converter

    config = OmegaConf.load(args.training_config.resolve())
    model = create_model(
        config.model,
        weight_path=args.checkpoint.resolve(),
        class_num=config.dataset.class_num,
    ).eval()
    image_size = [args.image_size, args.image_size]
    converter = create_converter(config.model.name, model, config.model.anchor, image_size, "cpu")
    adapter = MitYoloExportAdapter(model, converter.anchor_grid, converter.scaler).eval()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        adapter,
        torch.zeros(1, 3, args.image_size, args.image_size),
        args.output,
        input_names=["images"],
        output_names=["detections"],
        dynamic_axes={"images": {0: "batch"}, "detections": {0: "batch"}},
        opset_version=args.opset,
        dynamo=False,
    )


if __name__ == "__main__":
    main()
