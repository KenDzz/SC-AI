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
