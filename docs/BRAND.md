# Nhận diện thương hiệu Trung Nguyên Legend trong dashboard

Tài liệu này ghi lại cách giao diện `apps/frontend` áp dụng nhận diện của Tập đoàn Trung Nguyên Legend, để ai sửa UI sau cũng giữ được cùng một ngôn ngữ.

Nguồn:
- Website https://trungnguyenlegend.com (CSS theme `legend_child_theme`, logo, banner trang chủ), khảo sát tháng 10/2026.
- Bản thiết kế "Safety Monitor" trên Claude Design (`Safety Monitor.dc.html`). Bảng màu và bố cục hiện tại lấy từ bản này.

## 1. Thương hiệu nói gì

- **Kiến trúc thương hiệu.** Trung Nguyên Legend là thương hiệu tập đoàn, cao cấp. Dưới nó có các thương hiệu tiêu dùng: Trung Nguyên (khiên đỏ, chữ vàng chanh) và G7. Dashboard là công cụ nội bộ của nhà máy, nên theo **thương hiệu tập đoàn (Legend)**.
- **Biểu tượng.** Mặt trống đồng Đông Sơn: ngôi sao mặt trời ở tâm, các vành hoa văn đồng tâm.
- **Giọng điệu.** Khát vọng, trang trọng: "Cà phê năng lượng – Cà phê đổi đời".
- **Thị giác.** Nền tối màu espresso, chữ hoa kiểu khắc La Mã giãn chữ, dải băng tối chữ vàng, đường kẻ mảnh có hình thoi.

## 2. Bảng màu (token trong `tailwind.config.js`)

| Token | Giá trị | Dùng cho |
|---|---|---|
| `ink` | `#17110C` | Sidebar, thẻ tối (KPI đầu hàng, People in view, New rule, Frame pipeline), nút chính |
| `ink-soft` / `ink-raised` / `ink-edge` | `#2C2016` / `#221810` / `#33261B` | Hover nút chính, ô con và viền trên nền tối |
| `paper` | `#F3EDE3` | Nền trang |
| `surface` | `#FFFDF9` | Nền thẻ (`.panel`), ô nhập |
| `cream` / `sand` | `#FBF7F0` / `#F8F2E8` | Nền phụ, đầu bảng |
| `line` (+ `soft`, `muted`, `strong`) | `#E6DCCB` … | Viền thẻ, kẻ bảng, viền ô nhập |
| `bark-*` | `#1E150E` → `#A3927F` | Chữ trên nền sáng (900 tiêu đề, 800 nội dung, 500 phụ) |
| `husk-*` | `#FBF4E8` → `#6E5D4A` | Chữ trên nền tối |
| `gold-500` | `#C99A4A` | Vạch nhấn, hình thoi, viền nút phụ |
| `gold-300` / `gold-200` | `#E3BE74` / `#F3DEB0` | Chữ vàng trên nền tối, số KPI tối |
| `gold-700` / `gold-800` | `#8A5A0E` / `#5E3D08` | Liên kết và chữ vàng trên nền sáng |
| `crimson-600` / `crimson-700` | `#9E2A1F` / `#8E2219` | CRITICAL, nút "Confirm violation", số đếm NEW ở sidebar |
| `leaf-600` | `#3E8A52` | Camera đang chạy, công tắc bật, AI Mode REAL |

Quy tắc:

- **Không dùng `gold-500` cho chữ trên nền sáng** (tương phản thấp); dùng `gold-700`.
- **Mức độ (severity)** — `SEVERITY` trong `components/ui.tsx`: CRITICAL đỏ, HIGH vàng hổ phách, MEDIUM nâu nhạt, LOW xanh xám. Biểu đồ dùng đúng các màu `bar` này.
- **Trạng thái (status)** — `StatusPill`: NEW vàng, CONFIRMED đỏ, FALSE_POSITIVE xanh rêu, RESOLVED xanh xám.
- **AI Mode: DEMO** luôn là viên thuốc màu hổ phách ở thanh trên cùng, theo yêu cầu trong `docs/SPEC.md`.

## 3. Chữ

| Vai trò | Font | Ghi chú |
|---|---|---|
| Tiêu đề trang, số KPI, chữ thương hiệu | **Cinzel** (`font-display`) | Thay cho **Trajan Pro 3** (font thương mại website dùng). |
| Giao diện, nội dung | **Be Vietnam Pro** (`font-sans`) | Đủ dấu tiếng Việt. |
| Giờ, mã camera/sự cố, số đo | **JetBrains Mono** (`font-mono`) | |

**Cinzel không có dấu thanh tiếng Việt** (ơ, ư, ạ…ỹ). Mọi chỗ in chữ động bằng Cinzel phải qua `displayFont(text)` trong `lib/labels.ts`. Hàm này trả về `font-sans` khi chuỗi có các ký tự đó, ví dụ tiêu đề trang là tên camera "Camera dây chuyền hạt 01".

Ba font được tải qua `next/font/google` và tự host khi build, nên lúc chạy trong nhà máy không cần Internet.

## 4. Thành phần dùng chung

- `components/ui.tsx`:
  - Hiển thị: `Kpi` (thẻ sáng/tối), `SeverityTag`, `StatusPill`, `Snapshot` (ảnh từ API có token).
  - Điều khiển: `Switch`, `Segmented`.
  - Nút: `PrimaryButton`, `OutlineButton`, `GhostButton`, `DangerButton`.
  - Hoạ tiết: `Rule`, `Emblem`, `Diamond`, `LiveDot`, `RecDot`.
- `components/shell.tsx`:
  - Sidebar đánh số La Mã, có số sự cố NEW.
  - Thanh trên cùng có AI Mode và đồng hồ giờ nhà máy.
  - Breadcrumb và vùng nút hành động của trang.
  - Mở luồng sự kiện (SSE) và bật toast khi có cảnh báo mới.
- `components/providers.tsx`: toast và ngăn kéo xem xét sự cố, gọi qua `useApp()` từ bất kỳ trang nào.
- `components/incident-drawer.tsx`: ngăn kéo xem xét. Chỉ hiện các bước mà backend cho phép (`REVIEW_TRANSITIONS`).
- `lib/live.ts`: kênh sự kiện trong trang (`useIncidentEvents`), để các trang tự làm mới khi có sự cố mới hoặc vừa được xem xét.
- **`Emblem`** là hoạ tiết vẽ lại theo trống đồng, **không phải logo chính thức**. Khi có logo do phòng thương hiệu cấp, thay ở sidebar và trang đăng nhập.

## 5. Những gì cố ý chưa làm theo design

- **"Undo decision"**: backend coi quyết định review là một chiều và lưu vết (`OperatorFeedback`), nên ngăn kéo không có nút hoàn tác.
- Lớp phủ khung người/vùng trên ảnh camera vẫn do ai-worker vẽ sẵn vào snapshot, không vẽ lại ở trình duyệt.
- Ngôn ngữ giao diện vẫn là tiếng Anh.
