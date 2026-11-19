#!/usr/bin/env python3
"""Công cụ xuất trang HTML xem toàn bộ ứng viên lỗi gán nhãn (candidates.json) trong 1 màn hình.
Nhúng ảnh trực tiếp bằng Base64 và chỉ làm nổi bật (highlight) đúng cặp Box/Segment đang bị nghi ngờ!
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pngutil  # noqa: E402


def to_data_uri(path: Path, mime: str) -> str:
    if not path.is_file():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def make_highlighted_mask_uri(mask_path: Path, highlight_seg_ids: set[int]) -> str:
    """Tạo ảnh PNG mask đã tô màu tươi sáng cho các segment và làm nổi bật segment bị nghi ngờ."""
    if not mask_path.is_file():
        return ""
    w, h, pixels = pngutil.read_rgb(mask_path)
    out = bytearray(len(pixels))
    palette = [
        (255, 99, 132), (54, 162, 235), (255, 206, 86), (75, 192, 192),
        (153, 102, 255), (255, 159, 64), (46, 204, 113), (231, 76, 60),
        (52, 152, 219), (241, 196, 15), (155, 89, 182), (26, 188, 156),
    ]
    color_map: dict[int, tuple[int, int, int]] = {}
    for i in range(0, len(pixels), 3):
        sid = pixels[i] + pixels[i + 1] * 256 + pixels[i + 2] * 65536
        if sid == 0:
            continue
        if sid not in color_map:
            if sid in highlight_seg_ids:
                # Nếu có nhiều segment highlight thì mỗi cái 1 màu thật rực, hoặc màu Vàng/Cyan sáng
                color_map[sid] = palette[len(color_map) % len(palette)]
            else:
                # Segment bình thường thì làm tối đi để dễ nhìn segment lỗi
                c = palette[len(color_map) % len(palette)]
                color_map[sid] = (c[0] // 3, c[1] // 3, c[2] // 3)
        r, g, b = color_map[sid]
        out[i], out[i + 1], out[i + 2] = r, g, b

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        pngutil.write_rgb(tmp_path, w, h, bytes(out))
        return to_data_uri(tmp_path, "image/png")
    finally:
        tmp_path.unlink(missing_ok=True)


def generate_html_viewer(delivery_dir: Path, candidates_path: Path, out_html: Path):
    d = delivery_dir.resolve()
    cands = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"]
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    panoptic = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    cat_by_id = {c["id"]: c for c in panoptic["categories"]}
    thing_ids = {c["id"] for c in panoptic["categories"] if c.get("isthing")}
    img_info_by_name = {Path(im["file_name"]).stem: im for im in panoptic["images"]}
    ann_by_img_id = {a["image_id"]: a for a in panoptic["annotations"]}
    classes = {}
    for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            cid, cname = ln.strip().split(" ", 1)
            classes[int(cid)] = cname.strip()

    by_img: dict[str, list[dict]] = {}
    for c in cands:
        by_img.setdefault(c["image"], []).append(c)

    cards_html = []
    for idx, (img_name, img_cands) in enumerate(sorted(by_img.items()), start=1):
        im_info = img_info_by_name[img_name]
        W, H = im_info["width"], im_info["height"]
        img_uri = to_data_uri(d / manifest[img_name]["image"], "image/jpeg")

        # Tìm các chỉ số DET[x] và PAN[y] được nhắc tới trong gợi ý để chỉ vẽ nổi bật đúng các khung đó!
        hl_det_ids: set[int] = set()
        hl_pan_ids: set[int] = set()
        for c in img_cands:
            for m in re.findall(r"DET\[(\d+)\]", c["detail"]):
                hl_det_ids.add(int(m))
            for m in re.findall(r"PAN\[(\d+)\]", c["detail"]):
                hl_pan_ids.add(int(m))

        mask_uri = make_highlighted_mask_uri(d / manifest[img_name]["mask"], hl_pan_ids)

        label_path = d / manifest[img_name]["label"]
        svg_shapes = []
        box_list_items = []
        for b_idx, ln in enumerate(label_path.read_text(encoding="utf-8").splitlines()):
            if not ln.strip():
                continue
            parts = ln.split()
            cid = int(float(parts[0]))
            x, y, w, h = map(float, parts[1:5])
            cname = classes.get(cid, str(cid))
            px, py, pw, ph = (x - w / 2) * W, (y - h / 2) * H, w * W, h * H
            is_hl = (not hl_det_ids) or (b_idx in hl_det_ids)
            if is_hl:
                svg_shapes.append(
                    f'<rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
                    f'fill="rgba(255,46,46,0.12)" stroke="#ff2e2e" stroke-width="3"/>'
                    f'<rect x="{px:.1f}" y="{max(0.0, py - 18):.1f}" width="{min(float(W), len(cname)*8 + 65):.1f}" height="18" fill="#ff2e2e"/>'
                    f'<text x="{px + 4:.1f}" y="{max(13.0, py - 4):.1f}" fill="#ffffff" '
                    f'font-size="12" font-weight="bold">DET[{b_idx}]: {html.escape(cname)}</text>'
                )
                box_list_items.append(
                    f"<li><span style='color:#ff4d4d'><b>👉 DET[{b_idx}]: {html.escape(cname)}</b></span> "
                    f"({pw:.0f}x{ph:.0f}px)</li>"
                )
            else:
                # Các box khác không liên quan thì chỉ vẽ nét mảnh mờ, không hiện chữ để khỏi rối mắt
                svg_shapes.insert(
                    0,
                    f'<rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
                    f'fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="1"/>'
                )

        ann = ann_by_img_id[im_info["id"]]
        seg_list_items = []
        for s in ann["segments_info"]:
            if s["category_id"] in thing_ids and not s.get("iscrowd"):
                cname = cat_by_id[s["category_id"]]["name"]
                sx, sy, sw, sh = s["bbox"]
                is_hl = (not hl_pan_ids) or (s["id"] in hl_pan_ids)
                if is_hl:
                    svg_shapes.append(
                        f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{sw:.1f}" height="{sh:.1f}" '
                        f'fill="none" stroke="#00e676" stroke-width="3" stroke-dasharray="7,4"/>'
                        f'<rect x="{sx:.1f}" y="{min(float(H - 18), sy + sh):.1f}" width="{min(float(W), len(cname)*8 + 95):.1f}" height="18" fill="#00b248"/>'
                        f'<text x="{sx + 4:.1f}" y="{min(float(H - 4), sy + sh + 13):.1f}" fill="#ffffff" '
                        f'font-size="12" font-weight="bold">PAN[{s["id"]}]: {html.escape(cname)}</text>'
                    )
                    seg_list_items.append(
                        f"<li><span style='color:#00e676'><b>👉 PAN[{s['id']}]: {html.escape(cname)}</b></span> "
                        f"(area={s['area']}px)</li>"
                    )

        cand_badges = "".join(
            f"<div class='cand-item'><b>Gợi ý #{i+1}:</b> <code>{html.escape(c['suggested_type'])}</code> — {html.escape(c['detail'])}</div>"
            for i, c in enumerate(img_cands)
        )

        cards_html.append(f"""
        <div class="card">
          <div class="card-header">
            <h2>#{idx}. Ảnh: <code>{img_name}</code> ({W}x{H})</h2>
            {cand_badges}
          </div>
          <div class="media-row">
            <div class="img-box">
              <div class="img-title">1. Vùng nghi ngờ: Khung ĐỎ (Detection YOLO) vs Khung XANH LÁ ĐỨT NÉT (Panoptic)</div>
              <div style="position:relative; width:{W}px; height:{H}px;">
                <img src="{img_uri}" width="{W}" height="{H}" style="display:block;" />
                <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position:absolute; top:0; left:0;">
                  {''.join(svg_shapes)}
                </svg>
              </div>
            </div>
            <div class="img-box">
              <div class="img-title">2. Ảnh gốc sạch (Để nhìn rõ vật thật trong ảnh)</div>
              <img src="{img_uri}" width="{W}" height="{H}" style="display:block;" />
            </div>
            <div class="img-box">
              <div class="img-title">3. Mask Panoptic (Segment nghi ngờ được tô màu sáng rực)</div>
              <img src="{mask_uri}" width="{W}" height="{H}" style="display:block;" />
            </div>
          </div>
          <div class="lists-row">
            <div><b>Box YOLO liên quan (Đỏ):</b><ul>{''.join(box_list_items)}</ul></div>
            <div><b>Segment Panoptic liên quan (Xanh lá):</b><ul>{''.join(seg_list_items)}</ul></div>
          </div>
        </div>
        """)

    page = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8"/>
<title>Bảng Duyệt Ứng Viên Pha 2 ({len(by_img)} ảnh)</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #121824; color: #f0f4f8; margin: 20px; }}
  .card {{ background: #1c2536; border: 1px solid #303f5c; border-radius: 10px; padding: 16px; margin-bottom: 24px; }}
  .card-header h2 {{ margin: 0 0 8px 0; color: #ffd166; }}
  .cand-item {{ background: #26334d; padding: 8px 12px; border-left: 4px solid #ff8a3d; margin-bottom: 6px; border-radius: 4px; font-size: 15px; }}
  .media-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px; }}
  .img-box {{ background: #0f141e; padding: 8px; border-radius: 6px; border: 1px solid #2b3954; }}
  .img-title {{ font-size: 12px; color: #9fb3c8; margin-bottom: 6px; font-weight: bold; }}
  .lists-row {{ display: flex; gap: 32px; margin-top: 12px; font-size: 13px; background: #151c29; padding: 10px; border-radius: 6px; }}
  ul {{ margin: 4px 0 0 0; padding-left: 20px; }}
  code {{ background: #0b1018; padding: 2px 6px; border-radius: 4px; color: #4cc9f0; font-size: 14px; }}
</style>
</head>
<body>
  <h1>👁️ Bảng Duyệt Ảnh Ứng Viên Lỗi Gán Nhãn (Pha 2 & Đề Ẩn) — Tổng số: {len(by_img)} ảnh ({len(cands)} gợi ý)</h1>
  <p>Chỉ những Box Đỏ (Detection) và Khung Xanh Lá (Panoptic) bị nghi ngờ mới được tô đậm và gắn nhãn chữ để không bị rối mắt!</p>
  {''.join(cards_html)}
</body>
</html>"""

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(page, encoding="utf-8")
    print(f"Đã tạo bảng duyệt ảnh HTML tại: {out_html.resolve()}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Tạo trang HTML xem toàn bộ ứng viên lỗi gán nhãn")
    ap.add_argument("delivery", help="Thư mục delivery")
    ap.add_argument("--candidates", required=True, help="File candidates.json")
    ap.add_argument("--out", required=True, help="File HTML đầu ra (vd: runs/r9007/review_board.html)")
    args = ap.parse_args()
    generate_html_viewer(Path(args.delivery), Path(args.candidates), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
