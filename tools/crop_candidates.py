#!/usr/bin/env python3
"""Cắt ảnh quanh từng ứng viên để xem bằng mắt (công cụ review, KHÔNG phải validator).

Mỗi ứng viên ra 1 file PNG gồm hai nửa đặt cạnh nhau:
  - trái: ảnh gốc + box detection (box bị nghi tô đỏ, box khác vàng) kèm tên lớp
  - phải: ảnh gốc phủ màu segment panoptic (segment bị nghi tô đỏ) kèm tên lớp
Vùng cắt bao quanh box/segment bị nghi, nới rộng 40%, phóng to nếu ảnh nhỏ.

  python tools/crop_candidates.py runs/r9007/delivery --candidates runs/r9007/candidates.json --out runs/r9007/crops

Cần Pillow (pip install pillow). Dùng Pillow ở đây được phép vì đây là công cụ xem ảnh.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pngutil  # noqa: E402

RED = (255, 40, 40)
YELLOW = (255, 220, 0)
MIN_SIDE = 480  # phóng vùng cắt lên ít nhất cỡ này để nhìn rõ vật nhỏ


def load_delivery(d: Path):
    classes = {}
    for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            cid, name = line.split(maxsplit=1)
            classes[int(cid)] = name.strip()
    pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    cats = {c["id"]: c["name"] for c in pan["categories"]}
    images = {Path(i["file_name"]).stem: i for i in pan["images"]}
    anns = {a["image_id"]: a for a in pan["annotations"]}
    return classes, cats, images, anns


def read_boxes(label_path: Path, classes: dict, W: int, H: int) -> list[tuple[str, float, float, float, float]]:
    boxes = []
    if not label_path.is_file():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) != 5:
            continue
        c = int(float(p[0]))
        xc, yc, w, h = map(float, p[1:])
        boxes.append((classes.get(c, f"?{c}"), (xc - w / 2) * W, (yc - h / 2) * H, (xc + w / 2) * W, (yc + h / 2) * H))
    return boxes


def render(delivery: Path, cand: dict, ctx, out_path: Path) -> None:
    classes, cats, images, anns = ctx
    stem = cand["image"]
    info = images[stem]
    W, H = info["width"], info["height"]
    ann = anns[info["id"]]
    det_ids = {int(x) for x in re.findall(r"DET\[(\d+)\]", cand.get("detail", ""))}
    pan_ids = {int(x) for x in re.findall(r"PAN\[(\d+)\]", cand.get("detail", ""))}

    img = Image.open(delivery / "images" / f"{stem}.jpg").convert("RGB")
    boxes = read_boxes(delivery / "labels" / f"{stem}.txt", classes, W, H)
    seg_info = {s["id"]: s for s in ann["segments_info"]}

    # Phủ màu segment: segment bị nghi đỏ đậm, segment thing khác xanh nhạt.
    mw, mh, px = pngutil.read_rgb(delivery / "masks" / ann["file_name"])
    overlay = img.copy()
    ov = overlay.load()
    for y in range(mh):
        for x in range(mw):
            sid = pngutil.segment_id(px, (y * mw + x) * 3)
            if sid in pan_ids:
                r, g, b = ov[x, y]
                ov[x, y] = ((r + 2 * 255) // 3, g // 3, b // 3)
            elif sid in seg_info and not seg_info[sid].get("iscrowd"):
                r, g, b = ov[x, y]
                ov[x, y] = (r * 3 // 4, g * 3 // 4, (b + 255) // 2)

    left, right = img.copy(), overlay
    dl, dr = ImageDraw.Draw(left), ImageDraw.Draw(right)
    for k, (name, x1, y1, x2, y2) in enumerate(boxes):
        color = RED if k in det_ids else YELLOW
        dl.rectangle([x1, y1, x2, y2], outline=color, width=3 if k in det_ids else 1)
        dl.text((x1 + 3, max(0, y1 + 2)), f"{k}:{name}", fill=color)
    for sid in pan_ids:
        s = seg_info.get(sid)
        if s:
            x, y, w, h = s["bbox"]
            dr.rectangle([x, y, x + w, y + h], outline=RED, width=2)
            dr.text((x + 3, y + 2), cats.get(s["category_id"], "?"), fill=RED)

    # Vùng cắt: bao quanh box + segment bị nghi, nới 40%.
    rects = [boxes[k][1:] for k in det_ids if k < len(boxes)]
    rects += [(s["bbox"][0], s["bbox"][1], s["bbox"][0] + s["bbox"][2], s["bbox"][1] + s["bbox"][3])
              for sid in pan_ids if (s := seg_info.get(sid))]
    if rects:
        x1 = min(r[0] for r in rects); y1 = min(r[1] for r in rects)
        x2 = max(r[2] for r in rects); y2 = max(r[3] for r in rects)
        pad_x, pad_y = (x2 - x1) * 0.4 + 20, (y2 - y1) * 0.4 + 20
        crop = (max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y)), min(W, int(x2 + pad_x)), min(H, int(y2 + pad_y)))
    else:
        crop = (0, 0, W, H)
    left, right = left.crop(crop), right.crop(crop)
    scale = max(1.0, MIN_SIDE / min(left.size))
    if scale > 1:
        size = (int(left.width * scale), int(left.height * scale))
        left, right = left.resize(size, Image.LANCZOS), right.resize(size, Image.LANCZOS)

    sheet = Image.new("RGB", (left.width * 2 + 10, left.height + 24), (30, 30, 30))
    sheet.paste(left, (0, 24))
    sheet.paste(right, (left.width + 10, 24))
    ImageDraw.Draw(sheet).text((6, 6), f"{stem}  {cand['suggested_type']}  |  {cand.get('detail', '')}", fill=(255, 255, 255))
    sheet.save(out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Cắt ảnh quanh từng ứng viên để review bằng mắt")
    ap.add_argument("delivery", type=Path)
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="thư mục ghi PNG")
    args = ap.parse_args()
    cands = json.loads(args.candidates.read_text(encoding="utf-8"))["candidates"]
    ctx = load_delivery(args.delivery)
    args.out.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(cands, 1):
        name = f"{i:02d}_{c['image']}_{c['suggested_type']}.png"
        render(args.delivery, c, ctx, args.out / name)
        print(f"[{i}/{len(cands)}] {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
