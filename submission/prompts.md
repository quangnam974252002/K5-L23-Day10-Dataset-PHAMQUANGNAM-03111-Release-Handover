# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | <<>> | <<>> | <<>> | <<>> | <<>> |
| 2 | Đoàn Quang Minh | Claude Code | "Đo số ứng viên trên lô sạch và 2 seed phụ, so F1 chỉ luật với báo hết ứng viên, ghi số liệu vào REPORT" | Lần đầu viết lệnh shell sai (một lệnh `cat` thừa chờ input) nên bị treo, phải dừng và chạy lại | Số trong REPORT chép từ output `score_findings.py` và `candidates.json` do Claude chạy trên máy Minh; nhóm chưa chạy lại độc lập |
| 3 | Đoàn Quang Minh | Claude Code | "Viết công cụ cắt ảnh quanh từng ứng viên, vẽ box detection và phủ màu segment panoptic" (`tools/crop_candidates.py`) | Chưa phát hiện | Claude chạy trên 15 ứng viên seed 9007, cả 15 file PNG mở được và đúng vật bị nghi |
| 4 | Đoàn Quang Minh | Claude Code (xem ảnh COCO công khai) | "Xem 15 ảnh ứng viên seed 9007, ghi `confirmed`/`rejected` và nhận xét" | Claude tự ghi 4 dòng tin cậy thấp (1818, 14831, 15335, 19109) vì ảnh tối, ảnh nhỏ hoặc vật tràn khung | `review_log.csv` seed 9007 lấy nguyên kết quả Claude ghi; **chưa có người trong nhóm duyệt lại từng ảnh**. F1 lỗi gán nhãn sau review ≈ 0.5 |
