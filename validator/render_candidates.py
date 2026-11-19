#!/usr/bin/env python3
"""Công cụ xuất trang HTML xem ứng viên review (giao diện 2 khung ảnh gốc lớn, sạch sẽ, không còn gợi ý áp đặt).
Nhúng ảnh Base64 100%, mở được trên mọi máy tính/trình duyệt.
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


def generate_clean_html_viewer(delivery_dir: Path, candidates_path: Path, out_html: Path):
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

    # Gom theo ảnh (nếu 1 ảnh có nhiều dòng nghi ngờ)
    by_img: dict[str, list[dict]] = {}
    for c in cands:
        by_img.setdefault(c["image"], []).append(c)

    cards_html = []
    for idx, (img_name, img_cands) in enumerate(sorted(by_img.items()), start=1):
        im_info = img_info_by_name[img_name]
        W, H = im_info["width"], im_info["height"]
        img_uri = to_data_uri(d / manifest[img_name]["image"], "image/jpeg")

        hl_det_ids: set[int] = set()
        hl_pan_ids: set[int] = set()
        for c in img_cands:
            for m in re.findall(r"DET\[(\d+)\]", c.get("detail", "")):
                hl_det_ids.add(int(m))
            for m in re.findall(r"PAN\[(\d+)\]", c.get("detail", "")):
                hl_pan_ids.add(int(m))

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
            is_hl = b_idx in hl_det_ids
            if is_hl:
                svg_shapes.append(
                    f'<rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
                    f'fill="rgba(255,46,46,0.15)" stroke="#ff2e2e" stroke-width="3"/>'
                    f'<rect x="{px:.1f}" y="{max(0.0, py - 20):.1f}" width="{min(float(W), len(cname)*9 + 75):.1f}" height="20" fill="#ff2e2e"/>'
                    f'<text x="{px + 4:.1f}" y="{max(14.0, py - 5):.1f}" fill="#ffffff" '
                    f'font-size="13" font-weight="bold">DET[{b_idx}]: {html.escape(cname)}</text>'
                )
                box_list_items.append(
                    f"<li><span style='color:#ff4d4d'><b>DET[{b_idx}]: {html.escape(cname)}</b></span> "
                    f"({pw:.0f}x{ph:.0f}px)</li>"
                )
            else:
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
                is_hl = s["id"] in hl_pan_ids
                if is_hl:
                    svg_shapes.append(
                        f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{sw:.1f}" height="{sh:.1f}" '
                        f'fill="none" stroke="#00e676" stroke-width="3" stroke-dasharray="8,4"/>'
                        f'<rect x="{sx:.1f}" y="{min(float(H - 20), sy + sh):.1f}" width="{min(float(W), len(cname)*9 + 110):.1f}" height="20" fill="#00b248"/>'
                        f'<text x="{sx + 4:.1f}" y="{min(float(H - 5), sy + sh + 15):.1f}" fill="#ffffff" '
                        f'font-size="13" font-weight="bold">PAN[{s["id"]}]: {html.escape(cname)}</text>'
                    )
                    seg_list_items.append(
                        f"<li><span style='color:#00e676'><b>PAN[{s['id']}]: {html.escape(cname)}</b></span> "
                        f"(area={s['area']}px)</li>"
                    )

        cards_html.append(f"""
        <div class="card">
          <div class="card-header">
            <h2>#{idx}. Ảnh: <code>{img_name}</code> ({W}x{H})</h2>
          </div>
          <div class="media-row">
            <div class="img-box">
              <div class="img-title">1. Vị trí đối chiếu: Khung ĐỎ (Detection YOLO) vs Khung XANH LÁ ĐỨT NÉT (Panoptic)</div>
              <div style="position:relative; width:{W}px; height:{H}px;">
                <img src="{img_uri}" width="{W}" height="{H}" style="display:block;" />
                <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position:absolute; top:0; left:0;">
                  {''.join(svg_shapes)}
                </svg>
              </div>
            </div>
            <div class="img-box">
              <div class="img-title">2. Ảnh gốc sạch (Nhìn bằng mắt thường để tự đánh giá vật thể thật)</div>
              <img src="{img_uri}" width="{W}" height="{H}" style="display:block;" />
            </div>
          </div>
          <div class="lists-row">
            <div><b>Đối tượng Detection (Khung Đỏ):</b><ul>{''.join(box_list_items) or '<li><i>Không có box nào ở vùng nghi ngờ</i></li>'}</ul></div>
            <div><b>Đối tượng Panoptic (Khung Xanh lá):</b><ul>{''.join(seg_list_items)}</ul></div>
          </div>
        </div>
        """)

    page = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8"/>
<title>Bảng Duyệt Ảnh Ứng Viên ({len(by_img)} ảnh)</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #111827; color: #f9fafb; margin: 24px auto; max-width: 1400px; padding: 0 16px; }}
  h1 {{ color: #60a5fa; font-size: 26px; border-bottom: 2px solid #374151; padding-bottom: 12px; }}
  .card {{ background: #1f2937; border: 1px solid #374151; border-radius: 12px; padding: 20px; margin-bottom: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); }}
  .card-header h2 {{ margin: 0 0 12px 0; color: #f59e0b; font-size: 20px; }}
  .media-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin-top: 14px; }}
  .img-box {{ background: #0b0f19; padding: 10px; border-radius: 8px; border: 1px solid #374151; }}
  .img-title {{ font-size: 13px; color: #9ca3af; margin-bottom: 8px; font-weight: bold; }}
  .lists-row {{ display: flex; gap: 40px; margin-top: 16px; font-size: 14px; background: #111827; padding: 12px 16px; border-radius: 8px; border: 1px solid #374151; }}
  ul {{ margin: 6px 0 0 0; padding-left: 20px; }}
  code {{ background: #374151; padding: 2px 6px; border-radius: 4px; color: #60a5fa; font-family: monospace; font-size: 15px; }}
</style>
</head>
<body>
  <h1>👁️ Bảng Duyệt Ảnh Ứng Viên Lỗi Gán Nhãn — Tổng số: {len(by_img)} ảnh</h1>
  <p style="color:#9ca3af; font-size:15px;">Mỗi ảnh được đặt cạnh nhau 2 khung lớn nguyên bản: <b>(1) Vị trí đối chiếu đè Khung Đỏ (Detection) & Khung Xanh Lá (Panoptic)</b> và <b>(2) Ảnh gốc sạch</b> để người kiểm duyệt tự do nhìn mắt thật và kết luận khách quan.</p>
  {''.join(cards_html)}
</body>
</html>"""

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(page, encoding="utf-8")
    print(f"Đã tạo bảng duyệt ảnh sạch tại: {out_html.resolve()}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Tạo trang HTML xem ứng viên không kèm gợi ý áp đặt")
    ap.add_argument("delivery", help="Thư mục delivery")
    ap.add_argument("--candidates", required=True, help="File candidates.json")
    ap.add_argument("--out", required=True, help="File HTML đầu ra")
    args = ap.parse_args()
    generate_clean_html_viewer(Path(args.delivery), Path(args.candidates), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
