# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | <<>> | <<>> | <<>> | <<>> | <<>> |
| 2 | Đoàn Quang Minh | Claude Code | "Đo số ứng viên trên lô sạch và 2 seed phụ, so F1 chỉ luật với báo hết ứng viên, ghi số liệu vào REPORT" | Lần đầu viết lệnh shell sai (một lệnh `cat` thừa chờ input) nên bị treo, phải dừng và chạy lại | Số trong REPORT chép từ output `score_findings.py` và `candidates.json` do Claude chạy trên máy Minh; nhóm chưa chạy lại độc lập |
| 3 | Đoàn Quang Minh | Claude Code | "Viết công cụ cắt ảnh quanh từng ứng viên, vẽ box detection và phủ màu segment panoptic" (`tools/crop_candidates.py`) | Chưa phát hiện | Claude chạy trên 15 ứng viên seed 9007, cả 15 file PNG mở được và đúng vật bị nghi |
| 4 | Đoàn Quang Minh & Đào Vũ Ngọc Anh | Claude Code | "Hỗ trợ dựng bộ khung review và cắt ảnh ứng viên" | Claude phân loại nhầm nhiều ca người/vật đứng sau bị che thành instance_merge và bỏ sót bbox_drift của mèo | Nhóm mở trực tiếp file HTML và công cụ cắt ảnh để xem bằng mắt người thật: xác nhận lại 6 lỗi gán nhãn thực sự (thuyền, người, cừu, ngựa vằn, mèo, ghế) và loại bỏ 9 ca chồng lấn tự nhiên sang rejected. F1 lỗi gán nhãn sau khi người duyệt đạt 0.9. |
