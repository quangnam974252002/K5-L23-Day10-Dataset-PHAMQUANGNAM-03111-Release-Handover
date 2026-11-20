# Bảo mật khi làm việc

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp
Tuyệt đối không được sao chép dữ liệu ra USB hay gửi qua email cá nhân mang về nhà làm tiếp. Dữ liệu gán nhãn là tài sản bảo mật của dự án và khách hàng, việc tự ý đưa ra khỏi môi trường quản lý của công ty vi phạm nghiêm trọng thỏa thuận bảo mật NDA và tiềm ẩn nguy cơ rò rỉ dữ liệu, thất thoát thông tin. Nhờ người khác làm hộ cũng hoàn toàn sai quy định vì vi phạm nguyên tắc kiểm soát quyền truy cập và trách nhiệm cá nhân đối với công việc được giao. Thay vào đó, nếu tiến độ gấp cần báo cáo ngay với quản lý dự án (PM/Team Lead) để được phê duyệt làm thêm giờ (OT) tại văn phòng hoặc sử dụng giải pháp truy cập từ xa an toàn (VPN/VDI được cấp phép) trên thiết bị công ty.

## 2. Năm việc: được hay không
1. Mở job được giao trên máy công ty: ĐƯỢC. Đây là môi trường làm việc hợp lệ, an toàn và được cấp quyền chính thức để thực hiện công việc gán nhãn.
2. Chụp màn hình gửi người quen: KHÔNG ĐƯỢC. Vi phạm nghiêm trọng nghĩa vụ bảo mật dữ liệu khách hàng (NDA), có nguy cơ làm lộ thông tin nhạy cảm của dự án ra bên ngoài.
3. Chép lô ra USB: KHÔNG ĐƯỢC. Thiết bị lưu trữ ngoài không được kiểm soát có nguy cơ lây nhiễm mã độc, thất lạc thiết bị và vi phạm quy định chống thất thoát dữ liệu (DLP).
4. Dán nhãn thật lên chatbot: KHÔNG ĐƯỢC. Tuyệt đối không đưa dữ liệu nội bộ/dữ liệu dự án lên các chatbot hoặc dịch vụ AI công cộng bên ngoài máy chủ công ty vì nguy cơ rò rỉ dữ liệu vào tập huấn luyện công khai.
5. Đưa tài khoản CVAT cho đồng nghiệp: KHÔNG ĐƯỢC. Mỗi người phải chịu trách nhiệm với tài khoản định danh cá nhân của mình; chia sẻ tài khoản làm sai lệch nhật ký truy vết (audit trail) và trách nhiệm giải trình.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ
Khi phát hiện hình ảnh có khuôn mặt người nhìn rõ trong lô mà chưa được làm mờ theo đúng guideline bảo vệ quyền riêng tư (PII), hành động chuẩn mực là lập tức đặt trạng thái lô là **Hold** (giữ lại, tạm dừng phát hành) và báo cáo ngay cho Trưởng dự án (Project Manager / Data Protection Officer). Tuyệt đối không được tự ý can thiệp làm mờ thủ công hay tự tiện xóa ảnh khỏi lô, vì việc này làm sai lệch cấu trúc dữ liệu, hỏng checksum sha256 và phá vỡ quy trình xử lý dữ liệu chuẩn của hệ thống. Trong lô r9007 hiện tại, ví dụ ảnh 000000012639 có khuôn mặt người phụ nữ ngồi trên bãi cỏ lộ rõ, hoặc ảnh 000000005001 có khuôn mặt người đàn ông đeo kính cần phải đưa vào diện rà soát làm mờ trước khi được phát hành.
