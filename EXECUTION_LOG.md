# Nhật ký triển khai Challenge B

## Bổ sung bản web theo yêu cầu tiếp theo

- Đọc Sites skill và local preview workflow. Chọn ứng dụng localhost trong
  checkout hiện có vì B1/B2 cần Python process và filesystem trên máy.
- Viết/đọc `PROMPT_WEB_CHALLENGE_B.md` trước khi triển khai. Bổ sung callback tiến
  độ cho b1/b2, giữ nguyên đường thực thi và verification. Viết `webapp.py`,
  frontend ba màn chi tiết, history, inspector và export.
- Thêm `start-web.ps1`; server dùng thật tại 127.0.0.1:8766, không đụng server A.
- Kiểm tra ban đầu trong sandbox gặp WinError 10013 (loopback bị chặn); đã xin
  quyền và chạy server/HTTP tests/browser QA ngoài sandbox. Không quy lỗi sandbox
  thành lỗi của engine; không sửa hoặc bỏ test để che lỗi.
- `python -B -X utf8 run_checks.py`: **44/44 PASS**, gồm 31 tests cũ và 13 tests
  web qua HTTP thật. Log được runner ghi tại `output/tests.log`.
- `node scripts/browser-check.cjs` với Playwright trong bundled runtime và Edge:
  **14/14 browser checks PASS**, không có JS errors. Test dùng temporary server,
  các engine chạy thật; kiểm tra thông báo bận giả lập HTTP 409 riêng.
- Xem ảnh overview, request B1, table/context B2 và mobile. Tăng cỡ chữ, sửa
  cuộn về đầu khi đổi tab, chạy lại browser QA sau thay đổi giao diện.
- Khi chạy trên server bàn giao, Windows giữ file job.json khiến atomic rename
  bị PermissionError. Lưu log lần đó tại `output/web-qa/first-live-file-lock.log`.
  Bổ sung retry atomic rename với backoff và finally luôn giải phóng run gate;
  thêm 2 regression tests (khóa tạm thời và lỗi ghi kéo dài). Kết quả cuối là
  **44/44 tests PASS**. Lần lỗi cũ được giữ trong lịch sử, không giả thành PASS.
- Khởi động lại đúng server B, dừng preview tạm do agent tạo. Không đụng server
  A. Chạy lại bằng nút trên browser của server thật: **PASS** tại run
  `20261021T125501Z-31f6df8c`; có `output/web-qa/live-verification.json` và ảnh
  `08-live-demo.png`. Server thật 127.0.0.1:8766 được giữ chạy để người dùng demo.
- Cập nhật README và báo cáo, giữ nguyên bằng chứng CLI cũ. Demo web mặc định
  offline có quy tắc, API thật chỉ khả dụng khi môi trường server cấu hình rõ.

Phần dưới là nhật ký bản CLI ban đầu.

Ngày 21/10/2026, múi giờ người dùng UTC+7.

1. Kiểm tra workspace và hướng dẫn, liệt kê Challenge A. Đọc PDF skill, trích
   toàn bộ `../Challenge A/slide.pdf`, render/xem slide 32–33. Xem slide 18–31 và
   34 để thiết kế checkpoint, budget và Code Mode.
2. Đọc README, prompt, báo cáo, `memory_agent.py` và `chat_engine.py` của A. Chỉ
   tham khảo, không thay đổi file, DB hay server A. Không lấy key từ A.
3. Tạo và đọc lại `PROMPT_CHALLENGE_B.md`, tính SHA-256 trước khi triển khai.
   Prompt hash được lưu trong mọi verification của demo.
4. Đối chiếu OpenAI Docs cho adapter tùy chọn: trang Text generation và Counting
   tokens. Trang API reference quá lớn không fetch được, nên dùng hai guide đã
   fetch thành công. Không phát sinh API inference.
5. Viết B1: fixture có race thật, test đồng thời bằng Barrier, thực thi hai cách
   thử TTL/retry, event reducer, trigger budget, archive và checkpoint, worker
   process lạnh tiếp tục sửa lỗi và chạy 4 regression tests.
6. Viết B2: sinh 24 log với oracle theo công thức; program streaming SDK chạy
   trong process runtime riêng; kiểm tra code đã duyệt, path và budget; chỉ emit
   JSON cuối; build managed request và đáp án từ findings.
7. Viết API adapter tùy chọn và kiểm tra bằng mock. Không có biến môi trường
   OPENAI_API_KEY/OPENAI_MODEL khi kiểm tra cấu hình; default offline. Không có
   usage provider thật trong bằng chứng bàn giao.
8. Demo đầu đã PASS cả hai phần. Bổ sung oracle time ranges, test malformed,
   path escape, budget, checkpoint integrity references và API evaluation.
9. Lần test đầu gặp PermissionError ở thư mục TEMP mặc định của Windows sandbox.
   Đã chạy lại ngoài sandbox với quyền được cấp: 29/29 PASS. Sau đó sửa test để
   dùng thư mục tạm trong `Challenge B/tmp/tests`; bộ test chạy được trong
   workspace sandbox, không cần quyền ngoài cho các lần sau.
10. Chạy `run_checks.py` và demo: 29/29 PASS. Bổ sung hai test API evaluation
    (đúng request/context và từ chối câu trả lời sai), tổng thành 31 tests.
11. Chạy `.\run-demo.ps1` thật: **31/31 PASS**, B1 **8/8** checks, B2 **14/14**
    checks. B1 regression **4/4 PASS** sau cold resume. Lần bàn giao chuẩn:
    `output/demo/20261021T120236Z-17275980` (19:02:36 UTC+7).
12. Đọc lại REPORT, checkpoint, câu trả lời B2 và verification. Hoàn thiện README,
    báo cáo phân tích tiếng Việt và hướng dẫn cấu hình API. Không tạo chat khác,
    không dùng subagent, không thay đổi Challenge A.

## Lệnh xác minh đã chạy thành công

```powershell
python -B -X utf8 demo.py
python -B -X utf8 run_checks.py
.\run-demo.ps1
```

`output/tests.log` là output thực của runner, không chép tay kết quả test.
`output/tests-verification.json` lưu Python version, thời điểm và số test.
`output/LATEST_DEMO.txt` trỏ tới lần mới nhất; mỗi run có verification/report
được sinh từ dữ liệu thực thi. Số liệu bàn giao là bytes request, token là
heuristic có nhãn; không giả kết quả offline thành LLM/API usage.
