# Prompt bổ sung: demo Challenge B trên web

Yêu cầu trực tiếp: chạy và demo ngay trên web, vẫn đáp ứng đầy đủ Challenge B.

Tiếp tục từ bản CLI hiện có, giữ B1/B2 là nguồn thực thi duy nhất. Tạo ứng dụng
localhost bằng Python standard library và HTML/CSS/JS trong Challenge B. Không
phụ thuộc hay thay đổi ứng dụng Challenge A. Chạy server và mở URL cho người dùng.

## Trải nghiệm
- Giao diện tiếng Việt, dashboard rõ B1 Compact/B2 Code Mode, trạng thái chạy,
  history, nút chạy toàn bộ hoặc từng phần. Mỗi click tạo run/bằng chứng mới.
- B1: hiển thị trigger, budget/reserve, số event, bytes trước/sau, lỗi mở, cách
  thử, bước tiếp, constraints; test đỏ trước và xanh sau cold process, PID,
  checkpoint, request thật, patch và test log. Phân biệt archive với context.
- B2: hiển thị câu hỏi, file/records, top lỗi/service/time/evidence, Code Mode
  program và SDK trace, một JSON aggregate đi vào context, raw exclusion checks.
- Cho xem request thật, tải JSON và toàn bộ bằng chứng ZIP; xem raw sample chỉ
  trong inspector dành cho người xem, không chèn lại vào managed request.
- Live tiến độ dựa các phase thật. History tồn tại sau reload/restart. Khi lỗi,
  hiện lỗi và cho chạy lại. Không giả tiến độ, không giả kết quả test/API.
- Nhãn mặc định offline có quy tắc. Tùy chọn gọi adapter LLM hiện có chỉ khi env
  đã cấu hình, chỉ gửi managed contexts, hiển thị usage thật hoặc chưa đo.
- Responsive và dùng được bàn phím. Không yêu cầu API key cho demo mặc định.

## Thực thi và kiểm chứng
- Backend chạy b1.demo/b2.demo thật, background worker để UI không bị khóa. Cô
  lập thư mục mỗi run, một run đang chạy; validate input/path và chỉ serve file
  được cho phép; POST same origin. Không nhận code tùy ý từ trình duyệt.
- API tests qua HTTP server thật và browser QA bằng Playwright/Edge. Kiểm tra
  chạy B1+B2, từng phần, kiểm tra context thực, mở inspector, export/download,
  history/reload, mobile overflow, lỗi JS và trạng thái lỗi.
- Lưu log, ảnh QA, verification; cập nhật README/báo cáo/EXECUTION_LOG. Giữ bằng
  chứng CLI cũ. Viết và đọc prompt này trước khi triển khai web.
