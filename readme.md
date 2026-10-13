# AI Safety & Compliance Monitoring POC

Hệ thống xem camera nhà máy cà phê, đối chiếu luật an toàn, và tạo incident để người vận hành xác nhận. AI không ra quyết định kỷ luật.

Bản đặc tả gốc nằm ở [docs/SPEC.md](docs/SPEC.md).

## Chạy trên máy

Cần Docker Desktop. Trong thư mục dự án:

```text
copy .env.example .env
docker compose up -d --build
```

Lần đầu sẽ tải image và build, có thể mất vài phút.

Mở:

| Việc | Địa chỉ |
|---|---|
| Dashboard | http://localhost:3000 |
| API Swagger | http://localhost:8000/docs |
| MinIO console | http://localhost:9101 |
| Worker health | http://localhost:8081/health |

Postgres và Redis chỉ chạy trong mạng Docker, không mở cổng ra máy.

Tài khoản demo:

| Người dùng | Mật khẩu | Việc được làm |
|---|---|---|
| admin | admin123 | Camera, vùng, luật |
| safety | safety123 | Duyệt incident |
| viewer | viewer123 | Chỉ xem |

MinIO: `safetyadmin` / `safetyadmin123`.

## Bản đồ hệ thống

```mermaid
flowchart LR
  cam[RTSP hoặc MP4] --> worker[AI worker]
  worker --> detect[Phát hiện và theo dõi]
  detect --> zones[Vùng]
  zones --> rules[Luật]
  rules --> api[Backend]
  api --> db[(PostgreSQL)]
  api --> files[(MinIO)]
  api --> redis[(Redis)]
  redis --> ui[Dashboard]
  ui --> api
```

Worker xử lý hình tại chỗ. API chỉ nhận incident, ảnh, và cấu hình. Dashboard nhận incident mới qua Server-Sent Events.

## Năm tình huống mẫu

Dữ liệu khởi tạo có nhà máy Coffee Factory POC, bốn camera, năm vùng và năm luật:

1. Vùng cấm — người đứng trong vùng quá thời gian cấu hình.
2. Hairnet — chỉ trạng thái Không mới tạo incident. Không xác định thì không báo.
3. Đồng phục — chỉ trạng thái Sai mới tạo incident.
4. Vùng nguy hiểm máy — người đi vào polygon của máy.
5. Làn forklift — người đi vào làn. Xe forklift được vẽ để demo; cảnh báo dựa trên người.

Trong **AI Mode: DEMO**, worker tự tạo người đi vào từng vùng. Nhãn hairnet và đồng phục đi theo loại vùng, để buổi demo không cần file model. Banner trên dashboard ghi rõ đang ở DEMO.

Nút **Simulate an incident** trên trang camera giữ người đứng trong vùng vài giây để luật chạy ngay.

## Việc nên thử

1. Đăng nhập `admin`.
2. Mở một camera. Bật **Show AI overlay** để thấy người, vùng, hairnet và đồng phục.
3. Vào **Draw zones**, bấm các góc trên ảnh, lưu polygon.
4. Vào **Rules**, chọn mẫu luật và vùng.
5. Đợi khoảng 20 giây, hoặc bấm Simulate. Incident xuất hiện ở Overview mà không cần tải lại trang.
6. Mở incident, xem ảnh, bấm Confirm, False positive, hoặc Resolve.

Upload MP4 ở trang camera nếu muốn dùng video thật làm nền. Worker phát lại file đó. RTSP điền vào ô stream URL, dạng `rtsp://user:password@địa-chỉ/stream`. Mật khẩu không được ghi ra log và không trả về nguyên văn trên API.

## CPU và GPU

Mặc định chạy CPU. Dashboard không cần GPU.

`AI_MODE=REAL` dùng YOLOX-Nano khi có `models/person.onnx`, nhận diện toàn thân mà không yêu cầu thấy mặt. Cách tải model chính thức và checksum nằm ở [models/README.md](models/README.md). Không có model thì dùng OpenCV HOG. Khi chưa có `ppe.onnx`, hairnet và đồng phục dùng bộ phân loại màu dự phòng, chỉ phù hợp kiểm thử POC.

Đặt file ONNX vào thư mục `models/`:

| File | Hợp đồng |
|---|---|
| `person.onnx` | YOLOX-Nano chính thức: đầu vào 1x3x416x416 BGR 0..255, đầu ra raw 1x3549x85; class COCO 0 là người. |
| `forklift.onnx` | Ra tensor Nx6: x1, y1, x2, y2, score, class trong tọa độ ảnh đầu vào model. Class 1 là forklift. |
| `ppe.onnx` | Ảnh 128x128, 6 logit: hairnet Có/Không/Không xác định, rồi đồng phục Đúng/Sai/Không xác định. |

GPU trên máy Linux có NVIDIA Container Toolkit:

```text
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Image mặc định vẫn là CPU. Muốn inference CUDA thì cài `onnxruntime-gpu` trong image worker và giữ `AI_DEVICE=cuda`.

## Giấy phép model

- OpenCV và bộ HOG phát hiện người: Apache-2.0.
- Theo dõi người: ByteTrack qua thư viện supervision, Apache-2.0.
- ONNX Runtime: MIT.

Không dùng Ultralytics YOLO vì giấy phép AGPL.

## Theo dõi

- `http://localhost:8000/health`, `/ready`, `/metrics`
- `http://localhost:8081/health`, `/ready`, `/metrics`

Metric của worker gồm trạng thái camera, số frame, FPS, độ trễ inference, số phát hiện, số incident, và frame bị bỏ.

Trang Evaluation cho tỷ lệ false positive trên các incident đã được người duyệt. Đó chưa phải độ chính xác của model. Recall cần nhãn các vụ bị bỏ sót, POC này chưa thu thập phần đó.

## Dừng và xóa dữ liệu

Dừng, giữ database và ảnh:

```text
docker compose down
```

Xóa toàn bộ dữ liệu POC, gồm Postgres và MinIO:

```text
docker compose down -v
docker compose up -d --build
```

## Kiểm tra đã chạy

```text
docker compose ps
```

Backend và worker phải healthy. Đăng nhập xong phải thấy 4 camera và các incident mẫu.
