# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall), đo bằng `score_findings.py` (làm tròn 1 chữ số):

  | Seed | Chỉ lỗi luật | Lỗi luật + **báo hết** ứng viên (chưa xem ảnh) | Sau review mắt người (đối chiếu công cụ cắt ảnh và HTML board) |
  |---|---|---|---|
  | 9007 (luyện tập) | 1.0 / — / 0.8 (14 lỗi) | 1.0 / 0.4 / 0.7 (29 lỗi) | 1.0 / 0.9 / 1.0 (20 lỗi: 14 luật + 6 gán nhãn `confirmed`, 9 `rejected`) |
  | 1234 (seed phụ) | 1.0 / — / 0.7 (11 lỗi) | 1.0 / 0.5 / 0.8 (27 lỗi) | không review |
  | 4242 (seed phụ) | 1.0 / — / 0.7 (12 lỗi) | 1.0 / 0.4 / 0.7 (29 lỗi) | không review |

  Khi "báo hết", ứng viên `class_swap_or_category_swap` được tính là `class_swap` (chưa mở ảnh nên không biết bên nào sai).
- Số ứng viên trên lô sạch (`inject_release.py --seed 5 --no-faults`, 50 ảnh): **4**, cả 4 đều là `instance_merge` (2 ở ảnh `000000059044`, 1 ở `000000060899`, 1 ở `000000061171`).
- Hàng đợi trên seed luyện tập 9007: **15 ứng viên / 15 ảnh** (9 `instance_merge`, 3 `class_swap_or_category_swap`, 2 `bbox_drift`, 1 `missing_box`). Seed phụ: 1234 có 17, 4242 có 17. Hàng đợi đủ nhỏ để xem hết 15 ảnh.
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): ghép box ↔ segment bằng **tỉ lệ pixel mask nằm trong box** (không chỉ IoU bbox), bỏ segment `iscrowd`, bỏ vật nhỏ (segment < 600 px), bỏ ảnh đã dính lỗi luật (mỗi ảnh nhiều nhất một lỗi). Chi tiết ngưỡng trong `validator/cross_check.py`. Lô sạch cho thấy `instance_merge` là luật gây nhiễu nhiều nhất (4/4 ứng viên trên lô sạch), nên mọi ứng viên `instance_merge` đều phải mở ảnh kiểm kỹ: người đứng sau bị che thường làm một segment trùm vào hai box.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
F1 là trung bình điều hoà của precision và recall; báo thừa làm precision giảm y như bỏ sót làm recall giảm. Trên seed 9007, nộp thêm toàn bộ 15 ứng viên (không xem ảnh) làm F1 tổng **giảm từ 0.8 xuống 0.7**, F1 lỗi gán nhãn chỉ **0.4**: phần lớn ứng viên là lệch tự nhiên giữa detection và panoptic của COCO (người bị che, vật chồng nhau), không phải lỗi. Lô sạch không có lỗi nào vẫn sinh 4 ứng viên, đúng loại nhiễu đó. Ngoài ra, chưa xem ảnh thì không phân biệt được `class_swap` với `category_swap`, nên đoán một phía sẽ sai một phần. Chỉ giữ ứng viên đã `confirmed` sau khi xem ảnh thì giữ được recall mà không mất precision.

## 3. Quyết định và lineage
- **Kết quả QC v1 (`lab250_29f82c6d3554`):** Bộ kiểm phát hiện 20 lỗi (14 lỗi luật mức file + 6 lỗi gán nhãn thực tế) trên tổng số 250 ảnh. Tỉ lệ lỗi là **20 / 250 = 8.0%**.
- **Kết luận quyết định:** Theo quy chuẩn bàn giao dataset (ngưỡng lỗi cho phép $\le 2\%$), tỉ lệ lỗi 8.0% vượt xa ngưỡng chấp nhận. Do đó, quyết định chất lượng cho bản v1 là **HOLD** (giữ lại, không phát hành).
- **Phân tích độ ảnh hưởng (Blast Radius):**
  Lệnh `python scripts/lineage.py impact --release-id lab250_29f82c6d3554` trả về:
  `R-021: affected=True action=review_or_retrain`
- **Vì sao run `R-021` phải xem lại hoặc train lại?**
  Run huấn luyện `R-021` đã dùng trực tiếp dataset v1 làm dữ liệu đầu vào. Do v1 chứa các lỗi gán nhãn sai lệch (nhầm lớp đối tượng, trôi bounding box) và lỗi cấu trúc, mô hình đã học theo các mẫu dữ liệu bẩn đó. Việc phát hành phiên bản sửa lỗi v2 không thể tự động khắc phục các trọng số (weights) đã được huấn luyện của mô hình. Do đó, run `R-021` bắt buộc phải được đánh giá lại (review) hoặc huấn luyện lại hoàn toàn (retrain) trên dataset v2 sạch trước khi triển khai production.

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
- **Ticket (`incoming/ticket.md`):** model train trên lô v1 hay bỏ sót `cup` bị che hoặc ở mép ảnh; team AI thấy rõ ở `scene_303` và `scene_859`.
- **Nguyên nhân (`guideline/changelog.md`):** v1.3 chỉ đổi quy tắc của lớp `cup`: vật bị che trên 50% hoặc cắt ở mép ảnh **vẫn phải gán box**, còn v1.2 cho phép bỏ qua. Ảnh thuộc job làm theo v1.2 vì thế có thể thiếu box `cup`, và model học theo.
- **Tiêu chí:**
  - **Tầng a:** ảnh thuộc `scene_303` hoặc `scene_859`, nằm trong job có guideline **v1.2**, và có ít nhất một box detection lớp `cup` trong `labels/` của lô v1. Kết quả **4 ảnh**: `000000002157`, `000000002431` (scene_859), `000000002592`, `000000002685` (scene_303).
  - **Tầng b:** ảnh ở các cảnh khác, cùng điều kiện (job v1.2, có box `cup`), chưa được team AI báo. Kết quả **3 ảnh**: `000000003661` (scene_763), `000000003845`, `000000003934` (scene_454).
- **Vì sao lấy guideline theo job:** guideline được áp cho cả job khi job được tạo (ghi trong `jobs.csv`). Guideline ghi ở từng ảnh trong `metadata.json` có thể sai, chính là lỗi `guideline_mismatch` mà validator bắt. Lấy theo ảnh sẽ lọc sai tập ảnh. Theo `jobs.csv`, các job v1.2 là J01, J02, J03.
- **Báo ai:** cả 7 ảnh tầng a và b đều thuộc job **J02**, nên báo **A03** (người gán) và **Q01** (người kiểm). J01 (A03/Q03) và J03 (A05/Q01) cũng theo v1.2 nhưng không có ảnh nào có box `cup`, nên không nằm trong phạm vi báo. Các job khác của A03 (J04, J06) theo v1.3 nên không bị ảnh hưởng.
- **Hạn chế:** tiêu chí "có ít nhất một box `cup`" chỉ tìm được ảnh đã gán ít nhất một cốc. Ảnh v1.2 mà mọi cốc đều bị bỏ (không có box `cup` nào) sẽ không bị lọc ra; muốn tìm phải đối chiếu với panoptic (segment `cup` không có box tương ứng).

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
