"""Build the nine-class coffee detection set from public photos.

Does not use the colour detector. Two sources:

- dont-text-me/RoastedCoffeeDefectDataset (Apache-2.0). normal, frag, quaker,
  burnt, and the insect or mold token in the filename. "under" is dropped.
  The CSV merges insect and mold as insectormold; the filename token separates them.
- Mendeley 10.17632/ffhdwp4428.1 (CC BY 4.0), Yudha Auliya et al. Filename
  classes that match a worker id: normal, hitam, hitam sebagian, pecah,
  berlubang. Mixed-class frames and other SNI names are dropped.

Each photo is one bean on paper. The script cuts that bean out and pastes it
onto a dark belt so the pictures are closer to the factory camera. Fade and
sour are not in either set, so those two classes have no boxes.

--dense appends crowded scenes (about 18-40 px, nearly touching) without
deleting the single-bean and loose mosaic pictures. Those sizes match the
belt video after the worker letterboxes a 752 px frame into 640.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "coffee-yolo"
SOURCES = OUT / "_sources"
YORK = SOURCES / "roasted"
MENDELEY_ZIP = SOURCES / "mendeley-robusta.zip"
CANVAS = 640
VAL_FRACTION = 0.15
SEED = 2052

# Worker ids. Fade (3) and sour (4) are absent from these sets.
YORK_CLASS = {"normal": 0, "frag": 2, "quaker": 5, "burnt": 6}
GREEN_CLASS = {
    "biji normal": 0,
    "biji hitam": 1,
    "biji hitam sebagian": 1,
    "biji pecah": 2,
    "biji berlubang satu": 7,
    "biji berlubang lebih satu": 7,
    "biji berlubang lebih dari satu": 7,
}
CLASS_NAME = {
    0: "good",
    1: "black",
    2: "broken",
    3: "fade",
    4: "sour",
    5: "quaker",
    6: "burnt",
    7: "insect",
    8: "mould",
}
SINGLE_NAME = re.compile(r"^(.+?)_(\d+)_jpg\.rf\.[0-9a-f]+$", re.IGNORECASE)


def _york_rows() -> list[tuple[str, int, bytes | None]]:
    rows: list[tuple[str, int, bytes | None]] = []
    with (YORK / "beans.csv").open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            name = (record.get("img_name") or "").strip()
            defect = (record.get("defect_class") or "").strip().lower()
            path = YORK / "data" / name
            if not name or not path.exists():
                continue
            if defect == "insectormold":
                low = name.lower()
                if "-mold-" in low or "-mould-" in low:
                    class_id = 8
                elif "-insect-" in low:
                    class_id = 7
                else:
                    continue
            else:
                class_id = YORK_CLASS.get(defect)
                if class_id is None:
                    continue
            group = f"york:{Path(name).stem}"
            rows.append((group, class_id, path.read_bytes()))
    return rows


def _normalise_green(token: str) -> str:
    text = token.replace("-", " ").replace("_", " ").lower()
    return re.sub(r"\s+", " ", text).strip()


def _mendeley_rows() -> list[tuple[str, int, bytes | None]]:
    rows: list[tuple[str, int, bytes | None]] = []
    with zipfile.ZipFile(MENDELEY_ZIP) as archive:
        for name in archive.namelist():
            match = SINGLE_NAME.match(Path(name).stem)
            if match is None:
                continue
            class_id = GREEN_CLASS.get(_normalise_green(match.group(1)))
            if class_id is None:
                continue
            group = f"mendeley:{match.group(1)}_{match.group(2)}"
            rows.append((group, class_id, archive.read(name)))
    return rows


def _sprite(image: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _level, inverse = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = inverse > 0
    fraction = float(mask.mean())
    if fraction < 0.004 or fraction > 0.95:
        return None
    # A small dark blob on paper often includes the shadow. Keep the darker part.
    if 0.015 < fraction < 0.30:
        foreground = gray[mask]
        if foreground.size < 30:
            return None
        mask = mask & (gray <= float(np.percentile(foreground, 45)))
    mask_u8 = (mask & (gray < 210)).astype(np.uint8) * 255
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    mask_u8 = cv2.erode(mask_u8, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 80:
        return None
    x, y, width, height = cv2.boundingRect(contour)
    if width < 8 or height < 8 or max(width, height) / max(min(width, height), 1) > 4:
        return None
    return image[y : y + height, x : x + width].copy(), mask_u8[y : y + height, x : x + width].copy()


def _decode(blob: bytes) -> np.ndarray | None:
    image = cv2.imdecode(np.frombuffer(blob, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    return image


def _resize_sprite(sprite: np.ndarray, mask: np.ndarray, width: int) -> tuple[np.ndarray, np.ndarray]:
    scale = width / max(sprite.shape[1], 1)
    size = (max(8, int(round(sprite.shape[1] * scale))), max(8, int(round(sprite.shape[0] * scale))))
    return (
        cv2.resize(sprite, size, interpolation=cv2.INTER_AREA),
        cv2.resize(mask, size, interpolation=cv2.INTER_NEAREST),
    )


def _rotate(sprite: np.ndarray, mask: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray] | None:
    height, width = sprite.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
    bound_w = int(height * sine + width * cosine)
    bound_h = int(height * cosine + width * sine)
    matrix[0, 2] += bound_w / 2 - width / 2
    matrix[1, 2] += bound_h / 2 - height / 2
    rotated = cv2.warpAffine(sprite, matrix, (bound_w, bound_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    rotated_mask = cv2.warpAffine(mask, matrix, (bound_w, bound_h), flags=cv2.INTER_NEAREST, borderValue=0)
    ys, xs = np.where(rotated_mask > 0)
    if xs.size < 20:
        return None
    return rotated[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1], rotated_mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def _belt(rng: np.random.Generator) -> np.ndarray:
    blotch = cv2.resize(
        rng.normal(0, 12, (CANVAS // 20, CANVAS // 20)).astype(np.float32),
        (CANVAS, CANVAS),
        interpolation=cv2.INTER_LINEAR,
    )
    grain = rng.normal(0, 5, (CANVAS, CANVAS)).astype(np.float32)
    image = np.zeros((CANVAS, CANVAS, 3), np.float32)
    image[:, :, 0] = 32
    image[:, :, 1] = 50
    image[:, :, 2] = 34
    image += (blotch + grain)[:, :, None]
    return np.clip(image, 0, 255).astype(np.uint8)


def _overlaps(box: tuple[int, int, int, int], other: tuple[int, int, int, int]) -> bool:
    return box[0] < other[2] and box[2] > other[0] and box[1] < other[3] and box[3] > other[1]


def _iou(box: tuple[int, int, int, int], other: tuple[int, int, int, int]) -> float:
    x1 = max(box[0], other[0])
    y1 = max(box[1], other[1])
    x2 = min(box[2], other[2])
    y2 = min(box[3], other[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter <= 0:
        return 0.0
    area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
    other_area = max(1, (other[2] - other[0]) * (other[3] - other[1]))
    return inter / float(area + other_area - inter)


def _tint(sprite: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    gain = rng.uniform(0.8, 1.18, size=(1, 1, 3)).astype(np.float32)
    return np.clip(sprite.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def _place_dense(rng: np.random.Generator, sprites: list, count: int):
    """Paste small beans on a tight grid so neighbours nearly touch.

    `count` is only a ceiling. The grid pitch, not a random handful of slots,
    is what makes the belt look crowded.
    """
    canvas = _belt(rng)
    shift = int(rng.integers(-12, 6))
    canvas = np.clip(canvas.astype(np.int16) + shift, 0, 255).astype(np.uint8)
    bean_w = int(rng.integers(22, 36))
    step_x = bean_w + int(rng.integers(1, 9))
    step_y = bean_w + int(rng.integers(0, 8))
    occupied: list[tuple[int, int, int, int]] = []
    labels: list[str] = []
    y = int(rng.integers(0, 6))
    while y < CANVAS - 14 and len(labels) < count:
        x = int(rng.integers(0, 8))
        row_shift = int(rng.integers(0, max(1, step_x // 5)))
        while x < CANVAS - 14 and len(labels) < count:
            if rng.random() < 0.08:
                x += step_x
                continue
            sprite, mask, class_id = sprites[int(rng.integers(0, len(sprites)))]
            turned = _rotate(sprite, mask, float(rng.uniform(0, 360)))
            x += step_x
            if turned is None:
                continue
            sprite, mask = _resize_sprite(*turned, int(rng.integers(max(16, bean_w - 6), bean_w + 7)))
            sprite = _tint(sprite, rng)
            height, width = sprite.shape[:2]
            if width < 14 or height < 14 or width >= CANVAS - 4 or height >= CANVAS - 4:
                continue
            jx = int(rng.integers(-3, 4))
            jy = int(rng.integers(-3, 4))
            left = int(np.clip(x - step_x + row_shift + jx, 0, CANVAS - width))
            top = int(np.clip(y + jy, 0, CANVAS - height))
            box = (left, top, left + width, top + height)
            # Stay under the worker NMS IoU of 0.45 so neighbours are kept.
            if any(_iou(box, item) > 0.22 for item in occupied):
                continue
            alpha = (mask > 0).astype(np.float32)
            if float(alpha.mean()) < 0.35:
                continue
            alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
            view = canvas[top : top + height, left : left + width]
            if alpha.shape != view.shape[:2]:
                alpha = cv2.resize(alpha, (view.shape[1], view.shape[0]), interpolation=cv2.INTER_LINEAR)
            mixed = view.astype(np.float32) * (1.0 - alpha[:, :, None]) + sprite.astype(np.float32) * alpha[:, :, None]
            view[:] = np.clip(mixed, 0, 255).astype(np.uint8)
            occupied.append(box)
            labels.append(
                f"{class_id} {(left + width / 2) / CANVAS:.6f} {(top + height / 2) / CANVAS:.6f} "
                f"{width / CANVAS:.6f} {height / CANVAS:.6f}"
            )
        y += step_y
    if len(labels) < 80:
        return None
    return canvas, labels


def _place_beans(rng: np.random.Generator, beans: list[tuple[np.ndarray, np.ndarray, int]], width_low: int, width_high: int):
    canvas = _belt(rng)
    occupied: list[tuple[int, int, int, int]] = []
    labels: list[str] = []
    for sprite, mask, class_id in beans:
        turned = _rotate(sprite, mask, float(rng.uniform(0, 360)))
        if turned is None:
            continue
        sprite, mask = _resize_sprite(*turned, int(rng.integers(width_low, width_high)))
        height, width = sprite.shape[:2]
        if width >= CANVAS - 4 or height >= CANVAS - 4:
            continue
        origin = None
        for _ in range(30):
            x = int(rng.integers(0, CANVAS - width))
            y = int(rng.integers(0, CANVAS - height))
            box = (x - 2, y - 2, x + width + 2, y + height + 2)
            if all(not _overlaps(box, item) for item in occupied):
                origin = (x, y)
                break
        if origin is None:
            continue
        x, y = origin
        view = canvas[y : y + height, x : x + width]
        keep = mask > 0
        view[keep] = sprite[keep]
        occupied.append((x, y, x + width, y + height))
        labels.append(
            f"{class_id} {(x + width / 2) / CANVAS:.6f} {(y + height / 2) / CANVAS:.6f} {width / CANVAS:.6f} {height / CANVAS:.6f}"
        )
    if not labels:
        return None
    return canvas, labels


def _split_groups(rows: list[tuple[str, int, bytes]]) -> tuple[list, list]:
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)
    by_class: dict[int, list[str]] = defaultdict(list)
    for group, items in grouped.items():
        by_class[items[0][1]].append(group)
    rng = random.Random(SEED)
    train: list = []
    val: list = []
    for class_id, groups in by_class.items():
        rng.shuffle(groups)
        hold = 1 if len(groups) > 1 else 0
        hold = max(hold, int(round(len(groups) * VAL_FRACTION)))
        hold = min(hold, len(groups) - 1) if len(groups) > 1 else 0
        val_groups = set(groups[:hold])
        for group in groups:
            target = val if group in val_groups else train
            target.extend(grouped[group])
    return train, val


def _sprites(rows: list) -> list[tuple[np.ndarray, np.ndarray, int]]:
    found = []
    skipped = 0
    for _group, class_id, blob in rows:
        image = _decode(blob)
        sprite = None if image is None else _sprite(image)
        if sprite is None:
            skipped += 1
            continue
        found.append((sprite[0], sprite[1], class_id))
    return found, skipped


def _clear_output() -> None:
    for kind in ("images", "labels"):
        for split in ("train", "val"):
            folder = OUT / kind / split
            folder.mkdir(parents=True, exist_ok=True)
            for child in folder.iterdir():
                if child.name != ".gitkeep" and child.is_file():
                    child.unlink()


def _write(split: str, stem: str, canvas: np.ndarray, labels: list[str]) -> None:
    image_path = OUT / "images" / split / f"{stem}.jpg"
    label_path = OUT / "labels" / split / f"{stem}.txt"
    cv2.imwrite(str(image_path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    label_path.write_text("\n".join(labels) + "\n", encoding="utf-8")


def _clear_crowd() -> None:
    for kind in ("images", "labels"):
        for split in ("train", "val"):
            folder = OUT / kind / split
            if not folder.exists():
                continue
            for child in folder.glob(f"{split}-crowd-*"):
                if child.is_file():
                    child.unlink()


def _compose_dense(split: str, sprites: list, scenes: int, rng: np.random.Generator) -> Counter:
    counts: Counter = Counter()
    written = 0
    attempts = 0
    while written < scenes and attempts < scenes * 3:
        attempts += 1
        placed = _place_dense(rng, sprites, int(rng.integers(240, 420)))
        if placed is None:
            continue
        _write(split, f"{split}-crowd-{written:05d}", placed[0], placed[1])
        for line in placed[1]:
            counts[int(line.split(" ", 1)[0])] += 1
        written += 1
    counts["_scenes"] = written
    return counts


def _compose(split: str, sprites: list, mosaics: int, rng: np.random.Generator) -> Counter:
    counts: Counter = Counter()
    for index, (sprite, mask, class_id) in enumerate(sprites):
        placed = _place_beans(rng, [(sprite, mask, class_id)], 48, 150)
        if placed is None:
            continue
        _write(split, f"{split}-bean-{index:05d}", placed[0], placed[1])
        counts[class_id] += 1
    for index in range(mosaics):
        picks = [sprites[int(rng.integers(0, len(sprites)))] for _ in range(int(rng.integers(8, 15)))]
        placed = _place_beans(rng, picks, 34, 96)
        if placed is None:
            continue
        _write(split, f"{split}-mix-{index:05d}", placed[0], placed[1])
        for line in placed[1]:
            counts[int(line.split(" ", 1)[0])] += 1
    return counts


def _draw_labels(canvas: np.ndarray, labels: list[str]) -> np.ndarray:
    drawn = canvas.copy()
    for line in labels:
        class_id, cx, cy, width, height = [float(part) for part in line.split()]
        x1 = int((cx - width / 2) * CANVAS)
        y1 = int((cy - height / 2) * CANVAS)
        x2 = int((cx + width / 2) * CANVAS)
        y2 = int((cy + height / 2) * CANVAS)
        cv2.rectangle(drawn, (x1, y1), (x2, y2), (0, 255, 255), 1)
    return drawn


def build(check: bool, dense: int, dense_check: bool) -> None:
    if not (YORK / "beans.csv").exists() or not MENDELEY_ZIP.exists():
        raise SystemExit("missing sources under data/coffee-yolo/_sources")
    rows = _york_rows() + _mendeley_rows()
    train_rows, val_rows = _split_groups(rows)
    if check:
        picked: list = []
        seen: Counter = Counter()
        for row in train_rows:
            if seen[row[1]] >= 2:
                continue
            seen[row[1]] += 1
            picked.append(row)
        train_rows, val_rows = picked, val_rows[:4]
    if dense_check:
        train_rows = train_rows[:180]
    train_sprites, train_skip = _sprites(train_rows)
    val_sprites, val_skip = _sprites(val_rows if not dense_check else val_rows[:8])
    if not train_sprites or (not dense_check and not val_sprites):
        raise SystemExit(f"no sprites extracted (skipped train {train_skip}, val {val_skip})")
    if dense_check:
        preview = Path(r"C:\Users\TheAnh\AppData\Local\Temp\coffee-mask-check")
        preview.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(SEED)
        placed = _place_dense(rng, train_sprites, 360)
        if placed is None:
            raise SystemExit("dense check placement failed")
        dest = preview / "dense.jpg"
        cv2.imwrite(str(dest), _draw_labels(placed[0], placed[1]))
        print(dest)
        print("labels", len(placed[1]))
        return
    if dense > 0:
        _clear_crowd()
        rng = np.random.default_rng(SEED + 17)
        train_counts = _compose_dense("train", train_sprites, dense, rng)
        val_counts = _compose_dense("val", val_sprites, max(40, dense // 6), rng)
        print("dense_scenes", train_counts.pop("_scenes", 0), val_counts.pop("_scenes", 0))
        print("train_boxes", {CLASS_NAME[key]: train_counts[key] for key in sorted(CLASS_NAME)})
        print("val_boxes", {CLASS_NAME[key]: val_counts[key] for key in sorted(CLASS_NAME)})
        return
    if check:
        preview = Path(r"C:\Users\TheAnh\AppData\Local\Temp\coffee-mask-check")
        preview.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(SEED)
        placed = _place_beans(rng, train_sprites[:8], 40, 110)
        if placed is None:
            raise SystemExit("check placement failed")
        canvas, labels = placed
        dest = preview / "mosaic.jpg"
        cv2.imwrite(str(dest), _draw_labels(canvas, labels))
        print(dest)
        print("labels", len(labels), "skipped", train_skip)
        return
    _clear_output()
    rng = np.random.default_rng(SEED)
    train_counts = _compose("train", train_sprites, 1000, rng)
    val_counts = _compose("val", val_sprites, 160, rng)
    print("sprites", len(train_sprites), len(val_sprites), "skipped", train_skip, val_skip)
    print("train_boxes", {CLASS_NAME[key]: train_counts[key] for key in sorted(CLASS_NAME)})
    print("val_boxes", {CLASS_NAME[key]: val_counts[key] for key in sorted(CLASS_NAME)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dense", type=int, default=0, help="append this many crowded train scenes")
    parser.add_argument("--dense-check", action="store_true")
    args = parser.parse_args()
    build(args.check, args.dense, args.dense_check)


if __name__ == "__main__":
    main()
