# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | <<>> | <<>> | <<>> | <<>> | <<>> |
| 2 | Đoàn Quang Minh | Claude Code | "Đo số ứng viên trên lô sạch và 2 seed phụ, so F1 chỉ luật với báo hết ứng viên, ghi số liệu vào REPORT" | Lần đầu viết lệnh shell sai (một lệnh `cat` thừa chờ input) nên bị treo, phải dừng và chạy lại | Đối chiếu số trong REPORT với output thật của `score_findings.py` và `candidates.json` trên máy |
| 3 | Đoàn Quang Minh | Claude Code | "Viết công cụ cắt ảnh quanh từng ứng viên, vẽ box detection và phủ màu segment panoptic" (`tools/crop_candidates.py`) | <<ghi nếu phát hiện>> | Chạy trên 15 ứng viên seed 9007, mở từng PNG so với `review_board.html` |
| 4 | Đoàn Quang Minh | Claude Code (xem ảnh COCO công khai) | "Xem 15 ảnh ứng viên seed 9007 và soạn **nháp** nhận xét" (`runs/r9007/review_draft.csv`) | <<ghi các dòng người duyệt sửa lại so với nháp>> | Nháp **không** dùng trực tiếp: <<tên người>> mở lại từng ảnh, tự quyết `confirmed`/`rejected` và viết `review_log.csv`. Các dòng AI ghi tin cậy thấp (1818, 14831, 15335, 19109) được soi cả ảnh. |
