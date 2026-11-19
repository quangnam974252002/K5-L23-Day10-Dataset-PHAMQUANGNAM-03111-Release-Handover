#!/usr/bin/env python3
"""Module độc lập cho Pha 2: Đối chiếu Detection <-> Panoptic để sinh candidates.json.
Có thể chạy độc lập bằng CLI hoặc được import vào validator/validate.py của Pha 1 mà không gây conflict!
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pngutil  # noqa: E402


def bbox_iou(b1: list[float], b2: list[float]) -> float:
    """Tính IoU giữa 2 box dạng [x_min, y_min, width, height]."""
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    ix1, iy1 = max(x1, x2), max(y1, y2)
    ix2, iy2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = w1 * h1 + w2 * h2 - inter
    return inter / (union + 1e-12)


def get_flagged_from_rules(d: Path, rules_path: Path | None) -> set[str]:
    """Lấy danh sách ảnh đã dính lỗi luật từ file rules.json (nếu có) để loại trừ."""
    flagged: set[str] = set()
    if not rules_path or not Path(rules_path).is_file():
        return flagged
    errors = json.loads(Path(rules_path).read_text(encoding="utf-8")).get("errors", [])
    meta_list = json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]
    scene_to_imgs: dict[str, list[dict]] = {}
    for m in meta_list:
        scene_to_imgs.setdefault(m["scene_id"], []).append(m)

    for e in errors:
        if e["type"] == "scene_leak":
            imgs = scene_to_imgs.get(e["target"], [])
            splits = [m["split"] for m in imgs]
            if len(set(splits)) > 1:
                counts = {s: splits.count(s) for s in set(splits)}
                min_split = min(counts, key=counts.get)
                for m in imgs:
                    if m["split"] == min_split:
                        flagged.add(m["image"])
        else:
            flagged.add(e["target"])
    return flagged


def run_cross_check(delivery_dir: str | Path, candidates_out: str | Path, rules_json: str | Path | None = None) -> list[dict]:
    """Hàm chính sinh ứng viên lỗi gán nhãn từ thư mục delivery."""
    d = Path(delivery_dir)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    classes = {}
    for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            cid, cname = line.strip().split(" ", 1)
            classes[int(cid)] = cname.strip()
    panoptic = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    cat_by_id = {c["id"]: c for c in panoptic["categories"]}
    thing_ids = {c["id"] for c in panoptic["categories"] if c.get("isthing")}
    img_info_by_name = {Path(im["file_name"]).stem: im for im in panoptic["images"]}
    ann_by_img_id = {a["image_id"]: a for a in panoptic["annotations"]}

    flagged_images = get_flagged_from_rules(d, Path(rules_json) if rules_json else None)
    candidates: list[dict] = []

    for img_name in sorted(manifest.keys()):
        if img_name in flagged_images:
            continue
        it = manifest[img_name]
        img_path = d / it["image"]
        label_path = d / it["label"]
        mask_path = d / it["mask"]
        if not img_path.is_file() or not label_path.is_file() or not mask_path.is_file():
            continue

        im_info = img_info_by_name[img_name]
        W, H = im_info["width"], im_info["height"]
        ann = ann_by_img_id[im_info["id"]]
        if any(s["category_id"] not in cat_by_id for s in ann["segments_info"]):
            continue

        lines = [ln.strip() for ln in label_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        boxes = []
        valid_yolo = True
        for idx, ln in enumerate(lines):
            parts = ln.split()
            c = int(float(parts[0]))
            x, y, w, h = map(float, parts[1:5])
            if not (0 <= c < 80):
                valid_yolo = False
                break
            if (x - w / 2 < -0.001) or (y - h / 2 < -0.001) or (x + w / 2 > 1.001) or (y + h / 2 > 1.001):
                valid_yolo = False
                break
            boxes.append({
                "idx": idx, "class_id": c, "class_name": classes[c],
                "x": x, "y": y, "w": w, "h": h,
                "px_bbox": [(x - w / 2) * W, (y - h / 2) * H, w * W, h * H],
                "norm_area": w * h,
                "px_area": (w * W) * (h * H),
            })
        if not valid_yolo:
            continue

        # Loại trừ ảnh bị duplicate_box (phòng khi chưa truyền --rules)
        is_dup = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                b1, b2 = boxes[i], boxes[j]
                if b1["class_id"] == b2["class_id"]:
                    dw, dh = abs(b1["w"] - b2["w"]) * W, abs(b1["h"] - b2["h"]) * H
                    dx, dy = abs(b1["x"] - b2["x"]) * W, abs(b1["y"] - b2["y"]) * H
                    if dw < 0.05 and dh < 0.05 and 0.0 <= dx <= 2.6 and 0.0 <= dy <= 2.6 and (dx + dy > 0.1):
                        is_dup = True
                        break
            if is_dup:
                break
        if is_dup:
            continue

        mw, mh, pixels = pngutil.read_rgb(mask_path)
        seg_counts: dict[int, int] = {}
        for i in range(0, len(pixels), 3):
            sid = pixels[i] + pixels[i + 1] * 256 + pixels[i + 2] * 65536
            if sid:
                seg_counts[sid] = seg_counts.get(sid, 0) + 1

        # Loại trừ ảnh bị thing_overlap (phòng khi chưa truyền --rules)
        if any(
            s["category_id"] in thing_ids and not s.get("iscrowd")
            and s["area"] - seg_counts.get(s["id"], 0) >= max(5, int(s["area"] * 0.08))
            for s in ann["segments_info"]
        ):
            continue

        thing_segs = []
        for s in ann["segments_info"]:
            if s["category_id"] in thing_ids and not s.get("iscrowd"):
                thing_segs.append({
                    "id": s["id"],
                    "category_id": s["category_id"],
                    "class_name": cat_by_id[s["category_id"]]["name"],
                    "area": s["area"],
                    "bbox": [float(v) for v in s["bbox"]],
                })

        if not boxes and not thing_segs:
            continue

        seg_id_set = {s["id"] for s in thing_segs}
        overlap_px: dict[tuple[int, int], int] = {}
        for b in boxes:
            bx, by, bw, bh = b["px_bbox"]
            x0, y0 = max(0, int(bx)), max(0, int(by))
            x1, y1 = min(mw, int(bx + bw + 0.5)), min(mh, int(by + bh + 0.5))
            b_idx = b["idx"]
            for y in range(y0, y1):
                row_off = y * mw * 3
                for x in range(x0, x1):
                    idx = row_off + x * 3
                    sid = pixels[idx] + pixels[idx + 1] * 256 + pixels[idx + 2] * 65536
                    if sid in seg_id_set:
                        overlap_px[(sid, b_idx)] = overlap_px.get((sid, b_idx), 0) + 1

        # 1. INSTANCE_MERGE: 1 segment là segment khớp tốt nhất cho >= 2 box cùng lớp
        best_seg_of_box: dict[int, int] = {}
        for b in boxes:
            same_cls_segs = [s for s in thing_segs if s["class_name"] == b["class_name"]]
            if same_cls_segs:
                best_s = max(same_cls_segs, key=lambda s: overlap_px.get((s["id"], b["idx"]), 0) / (b["px_area"] + 1e-9))
                ov = overlap_px.get((best_s["id"], b["idx"]), 0)
                if ov >= 200 and (ov / (b["px_area"] + 1e-9)) >= 0.38:
                    best_seg_of_box[b["idx"]] = best_s["id"]

        for s in thing_segs:
            if s["area"] < 600:
                continue
            owned_boxes = [b for b in boxes if best_seg_of_box.get(b["idx"]) == s["id"]]
            if len(owned_boxes) >= 2:
                b1, b2 = owned_boxes[0], owned_boxes[1]
                ov1 = overlap_px.get((s["id"], b1["idx"]), 0)
                ov2 = overlap_px.get((s["id"], b2["idx"]), 0)
                if bbox_iou(b1["px_bbox"], b2["px_bbox"]) < 0.45:
                    candidates.append({
                        "image": img_name,
                        "suggested_type": "instance_merge",
                        "score": round((ov1 + ov2) / (s["area"] + 1e-9), 3),
                        "detail": f"Segment PAN[{s['id']}] lớp '{s['class_name']}' (area={s['area']}) gộp 2 box DET[{b1['idx']}] & DET[{b2['idx']}]",
                    })

        # 2. CLASS_SWAP / CATEGORY_SWAP: Box và Segment khớp chặt vị trí nhưng khác tên lớp
        for b in boxes:
            if b["norm_area"] < 0.003:
                continue
            for s in thing_segs:
                if s["area"] < 600:
                    continue
                iou = bbox_iou(b["px_bbox"], s["bbox"])
                ov = overlap_px.get((s["id"], b["idx"]), 0)
                seg_in_box = ov / (s["area"] + 1e-9)
                box_in_seg = ov / (b["px_area"] + 1e-9)
                if iou >= 0.42 and (seg_in_box >= 0.60 or box_in_seg >= 0.60) and b["class_name"] != s["class_name"]:
                    other_box_same_cls = any(
                        b2["class_name"] == s["class_name"] and bbox_iou(b2["px_bbox"], s["bbox"]) > 0.30
                        for b2 in boxes
                    )
                    other_seg_same_cls = any(
                        s2["class_name"] == b["class_name"] and bbox_iou(b["px_bbox"], s2["bbox"]) > 0.30
                        for s2 in thing_segs
                    )
                    if not other_box_same_cls and not other_seg_same_cls:
                        candidates.append({
                            "image": img_name,
                            "suggested_type": "class_swap_or_category_swap",
                            "score": round(iou, 3),
                            "detail": f"Box DET[{b['idx']}] ghi '{b['class_name']}' nhưng Mask PAN[{s['id']}] ghi '{s['class_name']}' (IoU={iou:.2f}, seg_in_box={seg_in_box:.2f})",
                        })

        # 3. BBOX_DRIFT: Box và Segment cùng lớp, khớp với nhau nhưng bị lệch tâm
        for b in boxes:
            if b["w"] < 0.06 or b["h"] < 0.06 or b["norm_area"] < 0.003:
                continue
            same_cls_segs = [s for s in thing_segs if s["class_name"] == b["class_name"]]
            if not same_cls_segs:
                continue
            best_s = max(same_cls_segs, key=lambda s: bbox_iou(b["px_bbox"], s["bbox"]))
            iou = bbox_iou(b["px_bbox"], best_s["bbox"])
            ov = overlap_px.get((best_s["id"], b["idx"]), 0)
            seg_in_box = ov / (best_s["area"] + 1e-9)

            same_cls_boxes = [b2 for b2 in boxes if b2["class_name"] == best_s["class_name"]]
            best_b = max(same_cls_boxes, key=lambda b2: bbox_iou(b2["px_bbox"], best_s["bbox"]))
            if best_b["idx"] != b["idx"]:
                continue

            bx, by, bw, bh = b["px_bbox"]
            sx, sy, sw, sh = best_s["bbox"]
            bcx, bcy = bx + bw / 2, by + bh / 2
            scx, scy = sx + sw / 2, sy + sh / 2
            center_shift = (((bcx - scx) / (sw + 1e-9)) ** 2 + ((bcy - scy) / (sh + 1e-9)) ** 2) ** 0.5
            area_ratio = (sw * sh) / (b["px_area"] + 1e-9)
            if 0.15 <= iou <= 0.85 and 0.15 <= seg_in_box <= 0.94 and 0.40 <= area_ratio <= 2.3 and center_shift >= 0.075:
                candidates.append({
                    "image": img_name,
                    "suggested_type": "bbox_drift",
                    "score": round(center_shift, 3),
                    "detail": f"DET[{b['idx']}] & PAN[{best_s['id']}] lớp '{b['class_name']}': lệch tâm={center_shift:.2f}, IoU={iou:.2f}, seg_in_box={seg_in_box:.2f}",
                })

        # 4. MISSING_BOX: Segment thing lớn, nhưng không có box nào phủ lên
        for s in thing_segs:
            norm_seg_bbox_area = (s["bbox"][2] * s["bbox"][3]) / (mw * mh)
            if norm_seg_bbox_area < 0.007 or s["area"] < 800:
                continue
            same_cls_ov = sum(overlap_px.get((s["id"], b["idx"]), 0) for b in boxes if b["class_name"] == s["class_name"])
            any_cls_max_iou = max((bbox_iou(b["px_bbox"], s["bbox"]) for b in boxes), default=0.0)
            if (same_cls_ov / (s["area"] + 1e-9)) < 0.15 and any_cls_max_iou < 0.30:
                candidates.append({
                    "image": img_name,
                    "suggested_type": "missing_box",
                    "score": round(norm_seg_bbox_area, 3),
                    "detail": f"Thiếu box cho segment PAN[{s['id']}] lớp '{s['class_name']}' (area={s['area']} px, chiếm {norm_seg_bbox_area*100:.1f}% ảnh)",
                })

    cand_path = Path(candidates_out)
    cand_path.parent.mkdir(parents=True, exist_ok=True)
    cand_path.write_text(json.dumps({"candidates": candidates}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Đã sinh {len(candidates)} ứng viên lỗi gán nhãn vào {cand_path}")
    return candidates


def main() -> int:
    ap = argparse.ArgumentParser(description="Chạy độc lập Pha 2: Đối chiếu Detection <-> Panoptic")
    ap.add_argument("delivery", help="Đường dẫn tới thư mục delivery")
    ap.add_argument("--candidates", required=True, help="File candidates.json đầu ra")
    ap.add_argument("--rules", help="File rules.json/errors.json của Pha 1 (nếu có) để loại trừ ảnh đã lỗi luật")
    args = ap.parse_args()
    run_cross_check(args.delivery, args.candidates, args.rules)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
