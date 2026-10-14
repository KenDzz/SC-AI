"""Export a trained Ultralytics checkpoint to models/coffee.onnx.

Train from the repo root, outside the worker image:

    pip install ultralytics
    yolo detect train model=yolov8n.pt data=tools/coffee_yolo/data.yaml imgsz=640 epochs=50
    python tools/coffee_yolo/export_coffee_onnx.py runs/detect/train/weights/best.pt

Label each bean yourself. Do not train on the colour-detector labels.
The worker reads the ONNX file with ONNX Runtime and does not import Ultralytics.
"""

import shutil
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tools/coffee_yolo/export_coffee_onnx.py path/to/best.pt")
    weights = Path(sys.argv[1])
    if not weights.exists():
        raise SystemExit(f"weights not found: {weights}")
    from ultralytics import YOLO

    model = YOLO(str(weights))
    exported = Path(model.export(format="onnx", imgsz=640, simplify=True))
    destination = Path(__file__).resolve().parents[2] / "models" / "coffee.onnx"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exported, destination)
    print(destination)


if __name__ == "__main__":
    main()
