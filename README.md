# Challenge B: Context management

## Demo ngay trên web

Mở **[Context Lab](http://127.0.0.1:8766)** khi server đang chạy. Khởi động lại:

```powershell
.\start-web.ps1
```

Hoặc chạy foreground: `python -B -X utf8 webapp.py --port 8766`.
Ứng dụng chỉ nghe trên localhost, không cần pip/npm hay API key để demo.
Đổi cổng bằng `start-web.ps1 -Port 8767` nếu 8766 đang được dùng.

1. Bấm **Chạy toàn bộ demo**. Web thực sự gọi Python để chạy B1 rồi B2; tiến độ
   lấy từ các phase thực thi, không phát lại kết quả đã ghi sẵn.
2. Vào **B1 · Compact**: xem lỗi, hai cách đã thử, next_action và constraints.
   Các tab **Test trước**, **Test sau** chứng minh test đỏ/xanh; **Request thật**
   là request cold process nhận. PID, trigger, budget và bytes đều hiển thị.
3. Vào **B2 · Code Mode**: xem top lỗi từ 24 file, count/service/time/evidence.
   Mở **Program run_code**, **SDK trace** hoặc **Request thật**. Bấm file:line
   để xem raw evidence trong inspector được gắn nhãn ngoài context.
4. Vào **Bằng chứng** để xem/tải checkpoint, request, test log, patch, oracle,
   verification và ZIP đầy đủ. ZIP có raw fixture để chấm offline; managed
   request vẫn chỉ có checkpoint/findings.
5. Có thể **chạy riêng B1/B2**, chuyển lịch sử và tải lại trang. Mỗi click tạo run
   mới trong `output/web-runs`; lịch sử còn sau restart server. Trên mobile,
   chọn lần chạy trong mục **Bằng chứng**.

Chế độ mặc định ghi rõ **offline có quy tắc**. Checkbox LLM chỉ bật khi server
được chạy với OPENAI_API_KEY/OPENAI_MODEL đã cấu hình; chọn checkbox và chạy toàn
bộ để đo usage thật, xem trong **Bằng chứng → LLM & cách đo**. Không nhập key
vào giao diện, không đọc key/DB của Challenge A. Nhãn token ước lượng và usage
provider được tách rõ.

Bản web dùng lại nguyên các demo/verification đã có; B1 mở process mới và sửa
fixture thật, B2 chạy program đã duyệt trong runtime riêng. Web không nhận code
tùy ý để chạy. Prompt bổ sung: [`PROMPT_WEB_CHALLENGE_B.md`](PROMPT_WEB_CHALLENGE_B.md).

Đã đạt **44/44 Python/HTTP tests** và **14/14 browser checks**, có ảnh desktop,
mobile và bằng chứng tải từ trình duyệt trong `output/web-qa`. Các API tests dùng
HTTP server thật; các lượt demo chạy engine thật. API LLM được mock trong test,
chưa có inference thật vì chưa cấu hình key/model.

Bài làm theo slide 32–33 trong `../Challenge A/slide.pdf`, gồm đầy đủ **B1:
Compact** và **B2: Code Mode**. Prompt đã viết trước khi triển khai:
[`PROMPT_CHALLENGE_B.md`](PROMPT_CHALLENGE_B.md).

## Chạy nhanh

Mở terminal tại thư mục `Challenge B`, dùng **Python 3.10 trở lên**, không cần pip:

```powershell
python -B -X utf8 demo.py
python -B -X utf8 run_checks.py
```

Hoặc chạy cả kiểm thử và demo bằng một lệnh:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-demo.ps1
```

Mỗi lần demo tạo một thư mục mới trong `output/demo/`, không ghi đè bằng chứng
trước đó. [`output/LATEST_DEMO.txt`](output/LATEST_DEMO.txt) ghi đường dẫn lần mới
nhất. Trong đó mở **`REPORT.md`** để xem số liệu và **`verification.json`** để xem
kết quả kiểm chứng. Báo cáo phân tích toàn bài: [`BAO_CAO_CHALLENGE_B.md`](BAO_CAO_CHALLENGE_B.md).

## Demo chứng minh gì?

**B1:** tạo session dài có raw tool logs. Một test thực sự tái hiện race condition
trong concurrent token refresh. Harness chạy hai cách thử TTL/retry, thấy vẫn
FAIL, ghi state rồi tự compact khi đạt budget. Checkpoint giữ lỗi, cách đã thử,
constraints và bước tiếp theo. Process mới chỉ đọc checkpoint và fixture code,
tiếp tục sửa critical section, chạy **4 regression tests PASS**. Log gốc ở
archive; không có archive trong thư mục cold-start.

**B2:** trả lời câu hỏi top 3 mã lỗi ERROR/FATAL trên **24 file, 9.648 dòng log**.
Agent phát `run_code` chứa chương trình Python. Chương trình chạy trong process
runtime riêng, đọc file qua SDK, gom nhóm, xếp hạng và chỉ trả **1 JSON findings**.
48 dòng hỏng được đếm riêng; raw payload/message không vào context. Oracle độc
lập tính theo công thức xác nhận count, service, time range; verifier kiểm tra
vị trí file:line của evidence. Xem `b2/answer.md` trong lần chạy mới nhất.

Agent mặc định là **offline có quy tắc**, ghi rõ trong artifact. B1 sửa một
fixture theo template được kiểm tra, B2 phát chương trình đã duyệt và định dạng
aggregate. Đây là chứng minh thực thi harness, không phải đánh giá năng lực suy
luận tổng quát của LLM. Code runtime chấp nhận đúng chương trình đã duyệt; process
riêng không phải security sandbox để chạy code tùy ý.

## Gọi LLM thật và ghi usage

Tùy chọn này cần `OPENAI_API_KEY` và `OPENAI_MODEL` trong môi trường terminal.
Đặt key qua công cụ quản lý bí mật hoặc biến môi trường của bạn; không lưu key
trong repo. Model là model có quyền sử dụng trên tài khoản, không có default
âm thầm thay thế.

```powershell
# Sau khi OPENAI_API_KEY và OPENAI_MODEL đã được cấu hình:
python -B -X utf8 demo.py --with-api
```

Hai request LLM chỉ chứa checkpoint B1 hoặc findings B2. API response và
`usage.input_tokens` thật được lưu trong `api/b1-response.json`,
`api/b2-response.json`, `api/verification.json` của lần chạy đó. B1 kiểm tra model
đọc đúng lỗi, failed attempts, constraints và next operation; B2 đối chiếu số
đếm với oracle. Các hành động sửa fixture và chạy Code Mode đã được kiểm chứng
offline riêng; không giả rằng LLM đã viết bản sửa hoặc tự sinh code runtime.

**Không gửi raw baseline lên API.** Vì thế chế độ API chỉ đo usage sau quản lý
context; không có chênh lệch usage baseline thật. Số token so sánh offline là
`ceil(UTF-8 bytes / 4)`, được gắn nhãn ước lượng. Phần trăm giảm là **bytes của
toàn request JSON**, không phải phần trăm giảm hóa đơn hay token provider.

Trong bằng chứng bàn giao chưa gọi API thật vì không có key/model môi trường.
Các test adapter API sử dụng mock và được phân biệt với kết quả gọi model thật.

## Các file chính

| File | Vai trò |
| --- | --- |
| `PROMPT_CHALLENGE_B.md` | Prompt phân tích, thiết kế và tiêu chí hoàn tất |
| `compaction.py` | Budget, reducer, KEEP/TRUNCATE/DROP, archive/checkpoint |
| `b1.py` | Điều tra thật, hai cách thử, compact, cold-start và sửa fixture |
| `fixtures/` | Fixture cố ý có lỗi và 4 regression tests; demo sửa bản copy |
| `programs/analyze_logs.py` | Chương trình Code Mode đã duyệt |
| `code_runtime.py` | SDK đọc log, process runner, giới hạn dữ liệu/output |
| `b2.py` | Sinh log/oracle, tool call, context, đáp án và verifier |
| `llm.py` | OpenAI Responses adapter và đánh giá context bằng LLM tùy chọn |
| `demo.py` | Tự vận hành hai phần, tạo báo cáo và verification |
| `tests/test_challenge_b.py` | Kiểm thử chức năng, lỗi và tích hợp process thật |
| `run_checks.py` | Lưu log kiểm thử thật và `output/tests-verification.json` |
| `EXECUTION_LOG.md` | Nhật ký thực hiện và mức độ kiểm chứng |

## Tích hợp với Challenge A

Đã tham khảo `memory_agent.py`, `chat_engine.py`, README, prompt và báo cáo A.
Bài B dùng lại cách tổ chức request, bằng chứng, cold-start và tùy chọn adapter,
nhưng tự triển khai state/checkpoint và Code Mode cho đúng mục tiêu B. Không phụ
thuộc DB, server, API key hay module của A; không thay đổi thư mục A.

Để tích hợp về sau: giữ system instructions và memory active được retrieve từ A,
đưa history hiện tại qua compactor B1, rồi inject checkpoint; chuyển công cụ đọc
log hàng loạt sang B2 trước khi trả kết quả cho model. Memory dự án và checkpoint
tiến độ là hai loại state khác nhau, cần được lưu tách và chọn đúng scope.
