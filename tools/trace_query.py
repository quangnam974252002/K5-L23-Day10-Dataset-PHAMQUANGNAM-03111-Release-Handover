"""Truy vết ticket: tier_a, tier_b, notify. Guideline lấy theo JOB (jobs.csv).

  python tools/trace_query.py delivery --scenes scene_478 scene_893 --cls book --out submission/de_an/trace.json
"""
import argparse
import csv
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("delivery", type=Path)
ap.add_argument("--scenes", nargs="+", required=True, help="cảnh team AI nêu trong ticket")
ap.add_argument("--cls", required=True, help="lớp bị đổi quy tắc trong changelog")
ap.add_argument("--old", default="v1.2", help="guideline cũ")
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
d = a.delivery

names = {}
for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
    if line.strip():
        cid, name = line.split(maxsplit=1)
        names[int(cid)] = name.strip()
target_ids = {k for k, v in names.items() if v == a.cls}
if not target_ids:
    raise SystemExit(f"không có lớp '{a.cls}' trong classes.txt")

with (d / "jobs.csv").open(encoding="utf-8-sig", newline="") as f:
    jobs = {r["job_id"]: r for r in csv.DictReader(f)}
manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]


def has_class(label: Path) -> bool:
    for line in label.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if not p:
            continue
        try:
            if int(float(p[0])) in target_ids:
                return True
        except ValueError:
            continue
    return False


tier_a, tier_b, people = [], [], set()
for m in meta:
    stem = Path(m["image"]).stem
    job = jobs.get(m["job_id"])
    if job is None or job["guideline"] != a.old:  # guideline theo JOB, không theo ảnh
        continue
    label = d / manifest[stem]["label"] if stem in manifest else d / "labels" / f"{stem}.txt"
    if not label.is_file() or not has_class(label):
        continue
    (tier_a if m["scene_id"] in a.scenes else tier_b).append(stem)
    people.update([job["annotator"], job["reviewer"]])

out = {"tier_a": sorted(tier_a), "tier_b": sorted(tier_b), "notify": sorted(people)}
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
