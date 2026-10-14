# Person detector used by REAL mode

The local `person.onnx` is the official YOLOX-Nano COCO model:

- Source: https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx
- Upstream project and license: https://github.com/Megvii-BaseDetection/YOLOX (Apache-2.0)
- SHA256: `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`
- Input: BGR float32, 0..255, shape 1x3x416x416, resized with top-left alignment and padding value 114.
- Output: raw YOLOX predictions, shape 1x3549x85. The person adapter decodes strides 8, 16 and 32 and keeps COCO person class 0.

The person detector does not require visible facial skin. Person confidence must exceed 0.55; overlapping boxes are suppressed using the highest confidence first.

Download from PowerShell in the project root:

```powershell
Invoke-WebRequest -Uri https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx -OutFile models/person.onnx
```

Model binaries are ignored by Git. Restart the AI worker after installing or replacing the model. Without a person model, REAL mode falls back to OpenCV HOG. PPE remains a separate classifier; the person model does not classify hairnets or uniforms.

## Coffee belt inspector

`coffee.onnx` is optional. REAL mode uses it when the file is present. Otherwise the worker segments beans on the belt by colour and shape.

Contract:

- Input: RGB float32, 0..1, NCHW. The spatial size is read from the model.
- Output is either `Nx6` (`x1, y1, x2, y2, score, class_id`) or an Ultralytics YOLO head of shape `(1, 13, anchors)`. The 13 channels are `cx, cy, w, h` plus one score for each class id below. The worker runs NMS itself.
- Class ids: 0 good, 1 black, 2 broken, 3 fade, 4 sour, 5 quaker, 6 burnt, 7 insect, 8 mould.
- Train outside the worker image. `python tools/coffee_yolo/prepare_public_beans.py` writes `data/coffee-yolo` from the Apache-2.0 York roast set and the CC BY 4.0 Mendeley robusta set (doi:10.17632/ffhdwp4428.1). Fade and sour have no matching public class there. Do not train on the colour-detector labels. From the repo root: `yolo detect train model=yolov8n.pt data=tools/coffee_yolo/data.yaml imgsz=640 epochs=50` then `python tools/coffee_yolo/export_coffee_onnx.py <best.pt>`.
- A green belt keeps classes 0–4. A roasted belt keeps 0 and 5–8. A count belt counts every returned bean and does not grade it.
- Each bean is counted once, when its centre crosses the horizontal mid-line of the zone while moving downward.

Green classes follow Gope et al., Scientific Reports 2024 (black, broken, fade, sour). Roasted classes follow the open York roast-defect set (quaker, burnt, insect, mould). Those public photos do not include fade or sour. Train outside this repo and export ONNX. Do not import Ultralytics into the worker.
