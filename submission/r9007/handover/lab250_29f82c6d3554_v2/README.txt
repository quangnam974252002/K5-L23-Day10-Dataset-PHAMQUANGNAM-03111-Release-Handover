Release: lab250_29f82c6d3554_v2
Parent: lab250_29f82c6d3554
Số ảnh: 240
Số nhãn: 1638
Guideline: v1.2 (J01-J03), v1.3 (J04-J10)
QC v1: 20/250 = 8.0%
Kết luận v1: Hold — tỉ lệ lỗi 8.0% vượt ngưỡng 2%, không Release
Kết luận v2: Release — đã tách 10 ảnh lỗi detection vào rework, sửa guideline_mismatch và scene_leak trong lô
Ghi chú:
  - Sửa scene_leak (đưa cả cảnh về một split): scene_818 -> split=train (đổi: 000000007977)
  - Sửa wrong_hash (ảnh còn nguyên, cập nhật hash trong manifest v2): 000000011760 (hash mới: 929474fc4adc38fbd6a3...); 000000024144 (hash mới: 5d0374a85c317f0b64b3...)
  - Sửa guideline_mismatch trong truyvet.csv theo guideline job: 000000012120, 000000013177
  - Ảnh rework giao lại (10 ảnh):
    * 000000002923 (class_swap) -> annotator=A03, reviewer=Q01
    * 000000008277 (duplicate_box) -> annotator=A03, reviewer=Q02
    * 000000011197 (bbox_out_of_bounds) -> annotator=A02, reviewer=Q02
    * 000000012639 (class_swap) -> annotator=A02, reviewer=Q02
    * 000000013774 (invalid_class) -> annotator=A03, reviewer=Q01
    * 000000014831 (bbox_drift) -> annotator=A03, reviewer=Q01
    * 000000020571 (invalid_class) -> annotator=A04, reviewer=Q03
    * 000000022935 (bbox_out_of_bounds) -> annotator=A04, reviewer=Q03
    * 000000024610 (missing_image) -> annotator=A04, reviewer=Q02
    * 000000025386 (missing_box) -> annotator=A04, reviewer=Q02
  - Ảnh lỗi panoptic (nhãn detection vẫn đúng, ở lại v2) — báo team panoptic:
    * 000000001818: instance_merge
    * 000000009590: invalid_category_id
    * 000000016249: thing_overlap
    * 000000016502: category_swap
    * 000000023781: thing_overlap
