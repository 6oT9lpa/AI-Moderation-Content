# MIT YOLO training and local ONNX runtime

The application does not import Ultralytics or any AGPL package. Training is isolated in the
official MIT-licensed `MultimediaTechLab/YOLO` checkout pinned to commit
`c4cb5f6f56102eceeaa7d75e23e1125cd0373eaf`. Production loads only a verified ONNX artifact
through ONNX Runtime.

## Dataset contract

Prepare a normal object-detection dataset outside Git. Its dataset YAML must point to train and
validation images and declare class names in exactly the same order later passed to the packaging
command. Only the detector classes allowed by `configs/policies/yolo_rules.yaml` may enter the
production manifest.

## Prepare and train

Use a dedicated virtual environment for the external trainer. The wrapper verifies both the pinned
commit and the MIT license before invoking the upstream command:

```powershell
python scripts/training/train_mit_yolo.py `
  --checkout E:\models\src\mit-yolo `
  --dataset-config E:\datasets\moderation-images\dataset.yaml `
  --device cuda --model v9-s --batch-size 4
```

Export the selected checkpoint to ONNX with the pinned upstream implementation. Verify the output
matrix layout against a real sample; the API deliberately does not guess whether objectness is
present or whether the matrix is transposed.

## Package for production

```powershell
python scripts/training/package_yolo_onnx.py `
  --onnx E:\models\runs\best.onnx `
  --output-dir E:\AI-Moderator\models\media\yolo\moderation-v1 `
  --model-name moderation-yolov9-s --model-version moderation-v1 `
  --class-name suspicious_qr --class-name fake_giveaway_banner
```

Set `YOLO_ENABLED=true`, `YOLO_MODEL_DIR` to that bundle, and choose `YOLO_DEVICE=cpu` or `cuda`.
For CUDA install `requirements-media-gpu.txt`; for CPU install `requirements-media.txt`. Health is
ready for CUDA only when ONNX Runtime actually activates `CUDAExecutionProvider`.

Benchmark the exact production provider and retain the JSON report with the model release:

```powershell
python -m scripts.media.benchmark_onnx_yolo `
  --model-dir E:\AI-Moderator\models\media\yolo\moderation-v1 `
  --image E:\datasets\moderation-images\benchmark.png `
  --device cuda --warmup 10 --iterations 100 `
  --output E:\models\reports\moderation-v1-gtx1650.json
```
