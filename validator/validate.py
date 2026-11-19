#!/usr/bin/env python3
"""Check nine rule-based issues in a delivery directory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pngutil  # noqa: E402

YOLO_ROUNDING_TOLERANCE = 1e-6


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def safe_delivery_path(delivery: Path, relative_path: str) -> Path:
    root = delivery.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"path escapes delivery: {relative_path}")
    return path


def find_missing_images(delivery: Path, manifest: dict) -> set[tuple[str, str]]:
    return {("missing_image", image) for image, files in manifest.items()
            if not safe_delivery_path(delivery, files["image"]).is_file()}


def find_wrong_hashes(delivery: Path, manifest: dict) -> set[tuple[str, str]]:
    errors = set()
    for image, files in manifest.items():
        for key in ("image", "label", "mask"):
            path = safe_delivery_path(delivery, files[key])
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != files[f"{key}_sha256"]:
                errors.add(("wrong_hash", image))
                break
    return errors


def read_yolo_labels(delivery: Path, manifest: dict) -> dict[str, list[tuple[int, float, float, float, float]]]:
    labels = {}
    for image, files in manifest.items():
        path = safe_delivery_path(delivery, files["label"])
        rows = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            values = line.split()
            if len(values) != 5:
                raise ValueError(f"{path.name}:{line_number}: expected 5 YOLO values")
            try:
                class_id = int(values[0])
                box = tuple(map(float, values[1:]))
            except ValueError as exc:
                raise ValueError(f"{path.name}:{line_number}: invalid YOLO value") from exc
            if not all(map(math.isfinite, box)):
                raise ValueError(f"{path.name}:{line_number}: box values must be finite")
            rows.append((class_id, *box))
        labels[image] = rows
    return labels


def find_invalid_classes(labels: dict[str, list[tuple]]) -> set[tuple[str, str]]:
    return {("invalid_class", image) for image, rows in labels.items()
            if any(not 0 <= row[0] < 80 for row in rows)}


def find_out_of_bounds_boxes(
    labels: dict[str, list[tuple]], image_sizes: dict[str, tuple[int, int]]
) -> set[tuple[str, str]]:
    errors = set()
    for image, rows in labels.items():
        width, height = image_sizes[image]
        for _, x, y, box_width, box_height in rows:
            # YOLO values are rounded to six decimals, so an edge can drift by 1e-6.
            if (x - box_width / 2 < -YOLO_ROUNDING_TOLERANCE
                    or x + box_width / 2 > 1 + YOLO_ROUNDING_TOLERANCE
                    or y - box_height / 2 < -YOLO_ROUNDING_TOLERANCE
                    or y + box_height / 2 > 1 + YOLO_ROUNDING_TOLERANCE):
                errors.add(("bbox_out_of_bounds", image))
                break
    return errors


def find_duplicate_boxes(
    labels: dict[str, list[tuple]], image_sizes: dict[str, tuple[int, int]]
) -> set[tuple[str, str]]:
    errors = set()
    for image, rows in labels.items():
        width, height = image_sizes[image]
        for index, first in enumerate(rows):
            for second in rows[index + 1:]:
                if (first[0] == second[0] and first[3:] == second[3:]
                        and abs(first[1] - second[1]) * width <= 2
                        and abs(first[2] - second[2]) * height <= 2):
                    errors.add(("duplicate_box", image))
                    break
            if ("duplicate_box", image) in errors:
                break
    return errors


def find_scene_leaks(metadata: list[dict]) -> set[tuple[str, str]]:
    scene_splits: dict[str, set[str]] = defaultdict(set)
    for row in metadata:
        scene_splits[row["scene_id"]].add(row["split"])
    return {("scene_leak", scene) for scene, splits in scene_splits.items()
            if {"train", "val"} <= splits}


def find_guideline_mismatches(metadata: list[dict], jobs: dict[str, str]) -> set[tuple[str, str]]:
    errors = set()
    for row in metadata:
        if row["job_id"] not in jobs:
            raise ValueError(f"metadata references unknown job {row['job_id']}")
        if row["guideline_version"] != jobs[row["job_id"]]:
            errors.add(("guideline_mismatch", Path(row["image"]).stem))
    return errors


def find_invalid_category_ids(panoptic: dict) -> set[tuple[str, str]]:
    categories = {item["id"] for item in panoptic.get("categories", [])}
    errors = set()
    for annotation in panoptic.get("annotations", []):
        image = Path(annotation["file_name"]).stem
        if any(segment["category_id"] not in categories
               for segment in annotation.get("segments_info", [])):
            errors.add(("invalid_category_id", image))
    return errors


def find_thing_overlaps(delivery: Path, panoptic: dict) -> set[tuple[str, str]]:
    thing_categories = {item["id"] for item in panoptic.get("categories", [])
                        if item.get("isthing") == 1}
    masks_dir = (delivery / "masks").resolve()
    errors = set()
    for annotation in panoptic.get("annotations", []):
        image = Path(annotation["file_name"]).stem
        mask_path = (masks_dir / annotation["file_name"]).resolve()
        if not mask_path.is_relative_to(masks_dir):
            raise ValueError(f"mask path escapes delivery/masks: {annotation['file_name']}")
        _, _, pixels = pngutil.read_rgb(mask_path)
        pixel_counts = Counter(
            pngutil.segment_id(pixels, offset) for offset in range(0, len(pixels), 3)
        )
        if any(
            segment["category_id"] in thing_categories
            and not segment.get("iscrowd", 0)
            and segment["area"] > pixel_counts[segment["id"]]
            for segment in annotation.get("segments_info", [])
        ):
            errors.add(("thing_overlap", image))
    return errors


def collect_errors(delivery: Path) -> list[dict[str, str]]:
    manifest = load_json(delivery / "manifest.json").get("items")
    metadata = load_json(delivery / "metadata.json").get("items")
    panoptic = load_json(delivery / "panoptic.json")
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must contain an items object")
    if not isinstance(metadata, list):
        raise ValueError("metadata.json must contain an items list")
    with (delivery / "jobs.csv").open(encoding="utf-8-sig", newline="") as file:
        jobs = {row["job_id"]: row["guideline"] for row in csv.DictReader(file)}

    images = {Path(item["file_name"]).stem: (item["width"], item["height"])
              for item in panoptic.get("images", [])}
    labels = read_yolo_labels(delivery, manifest)
    errors = find_missing_images(delivery, manifest)
    errors.update(find_wrong_hashes(delivery, manifest))
    errors.update(find_invalid_classes(labels))
    errors.update(find_out_of_bounds_boxes(labels, images))
    errors.update(find_duplicate_boxes(labels, images))
    errors.update(find_scene_leaks(metadata))
    errors.update(find_guideline_mismatches(metadata, jobs))
    errors.update(find_invalid_category_ids(panoptic))
    errors.update(find_thing_overlaps(delivery, panoptic))
    return [{"type": kind, "target": target} for kind, target in sorted(errors)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate delivery metadata and panoptic labels")
    parser.add_argument("delivery", type=Path, help="delivery directory")
    parser.add_argument("--out", type=Path, required=True, help="output errors.json path")
    parser.add_argument("--candidates", type=Path, help="optional candidates output (empty in phase 1)")
    args = parser.parse_args()

    delivery = args.delivery.resolve()
    if not delivery.is_dir():
        parser.error(f"delivery directory does not exist: {delivery}")
    errors = collect_errors(delivery)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"errors": errors}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.candidates:
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        args.candidates.write_text('{"candidates": []}\n', encoding="utf-8")
    print(f"Wrote {len(errors)} findings to {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"validate.py: {exc}") from exc
