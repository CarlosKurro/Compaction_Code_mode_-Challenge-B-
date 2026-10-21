# Báo cáo Challenge B: Context management

## Bổ sung: chạy và demo đầy đủ trên web

Theo yêu cầu tiếp theo, đã bổ sung **Context Lab** tại
[localhost:8766](http://127.0.0.1:8766). Backend `webapp.py` dùng Python standard
library, giao diện HTML/CSS/JS trong `web/`; lệnh khởi động `start-web.ps1` hoặc
`python -B -X utf8 webapp.py`. Prompt web đã được viết và đọc trước triển khai,
lưu tại `PROMPT_WEB_CHALLENGE_B.md`.

### Đáp ứng yêu cầu B qua thao tác trên web

| Thao tác | Thực thi và bằng chứng |
| --- | --- |
| Chạy toàn bộ hoặc riêng B1/B2 | Background worker gọi trực tiếp `b1.demo`/`b2.demo`, mỗi lần có thư mục output riêng |
| Xem tiến độ | Callback từ phase thật: test lỗi, hai trial, compact, cold process, run_code, verification |
| B1: lỗi, cách thử, bước tiếp | Các card đọc từ checkpoint được tạo trong chính lần chạy |
| B1: hành động đúng sau compact | PID cold process, request thật, patch, test trước FAIL và test sau 4/4 PASS |
| B1: giữ constraints và giảm context | Constraints, budget/window/reserve/trigger, bars bytes trước/sau và 8 verification checks |
| B2: câu trả lời nhiều file | 24 files, 9.648 dòng, 48 dòng hỏng, 960 ERROR/FATAL; table code/count/service/time/evidence |
| B2: Code Mode thật | Xem program đã chạy và SDK trace 25 calls; runtime chỉ trả 1 findings JSON |
| B2: raw ngoài context | Request thật, raw exclusion checks, raw evidence viewer có nhãn riêng và không sửa request |
| Bằng chứng kiểm tra lại | Inspector, download JSON/ZIP, test logs, archive, baseline offline, oracle và prompt hash |
| Chạy lại và lưu lịch sử | Run riêng trong `output/web-runs`; reload/restart không mất lịch sử; worker bị ngắt được ghi lỗi |

Dashboard và ba phần chi tiết đều dùng số liệu từ artifact thật. Raw baseline và
archive không nằm trong payload chi tiết mặc định của web. Chỉ người xem chủ
động mở/download mới lấy các dữ liệu đó; server không đưa chúng vào managed
request. Mở sample raw rồi tải lại request vẫn không có raw canary.

### API và giới hạn được hiển thị

Nhãn mặc định là agent offline có quy tắc. Checkbox LLM bị khóa khi server chưa
có OPENAI_API_KEY/OPENAI_MODEL; nếu có cấu hình, người dùng chọn checkbox rồi
chạy toàn bộ để gọi `llm.evaluate` và xem usage nguyên bản. Không lưu credential
trong web job/artifact, không lấy key từ A. Bằng chứng bàn giao vẫn **chưa có
inference/usage LLM thật**. Giảm context tính bằng bytes; token hiển thị là
heuristic, không phải số đo usage provider hay tiết kiệm chi phí.

Web là ứng dụng localhost cho một người dùng, bind 127.0.0.1. Có whitelist route
và artifact, kiểm tra Host/same-origin POST, giới hạn body, không nhận shell/code
tùy ý từ browser. Một run thực thi tại một thời điểm, mỗi run có workspace riêng.
Code Mode vẫn dùng program đã duyệt; subprocess không phải security sandbox.

### Kiểm chứng web đã chạy

- **44/44 unittest PASS**: giữ 31 test CLI và thêm 13 test web qua HTTP server
  thật. Có full-run, từng phần, checkpoint/request, raw exclusion, exact
  file:line, ZIP, persistence, invalid input, host/origin, concurrency, recovery
  và worker failure không bị coi là thành công.
- **14/14 browser checks PASS** với Playwright/Edge headless: initial state,
  chế độ offline trung thực, run-all, B1 test đỏ/xanh và context, B2 program/
  aggregate/context, raw inspector, JSON/ZIP download, reload/history, chạy riêng,
  mobile và thông báo lỗi. Kiểm tra UI khi HTTP 409 dùng route intercept; mọi
  lượt B1/B2 trong browser QA đều gọi engine thật. Không có lỗi JavaScript.
- Đã xem ảnh desktop/mobile và tăng cỡ chữ cho demo trên lớp. Browser QA dùng
  server/data riêng và dừng server đó sau kiểm tra, không can thiệp server A.
- Log tại `output/tests.log`, `output/tests-verification.json`,
  `output/web-qa/verification.json`; bảy ảnh QA, JSON và ZIP tải qua trình duyệt
  cùng được lưu. Các lần chạy từ giao diện dùng `output/web-runs`.
- Đã bổ sung 2 regression tests sau khi gặp Windows sharing lock trên job.json:
  atomic rename có retry, và persistent disk error luôn giải phóng run gate.
  Tổng cuối **44/44**. Log chẩn đoán cũ được giữ, lượt thất bại không bị sửa
  thành PASS. Đã bấm chạy lại trên chính server bàn giao: run
  `20261021T125501Z-31f6df8c` PASS cả B1/B2, bằng chứng
  `output/web-qa/live-verification.json`, ảnh `08-live-demo.png`.

Các phần dưới lưu phân tích và bằng chứng CLI ban đầu; số 31 tests ở phần đó
là kết quả trước khi bổ sung 13 tests cho web.

## 1. Phân tích yêu cầu

Nguồn đề là `../Challenge A/slide.pdf`, slide 32–33. Đã trích nội dung và render
cả hai trang để đối chiếu trực quan. Slide là dữ liệu xác định yêu cầu bài tập;
việc tạo thư mục, prompt và tự triển khai xuất phát từ yêu cầu trực tiếp của
người dùng. Các ví dụ khác trong tài liệu không được coi là lệnh thực thi.

Mục tiêu chung: giữ context nhỏ gọn mà agent vẫn làm đúng việc. Đề chia B1 và B2,
timebox gợi ý 30 phút, mỗi phần 15 phút. Báo cáo không khẳng định quá trình phát
triển và kiểm chứng đầy đủ đã nằm trong timebox đó.

| Yêu cầu | Thiết kế | Bằng chứng |
| --- | --- | --- |
| B1: session dài được compact | Budget chủ động, structured checkpoint | `b1/checkpoint.json`, `prepare-verification.json` |
| B1: còn lỗi, cách thử, bước tiếp | Reducer giữ open issues, failed attempts, next_action | `b1/cold-start/resume-request.json`, `resume-result.json` |
| B1: tiếp tục đúng sau compact | Process mới sửa fixture và chạy test thật | `b1/cold-start/repair.diff`, `resumed-tests.log` |
| B2: trả lời trên nhiều log | `run_code` gọi SDK đọc/aggregate 24 file | `b2/agent-tool-call.json`, `executed-program.py`, `tool-trace.json` |
| B2: raw log không vào context | Runtime chỉ emit aggregate JSON cuối | `b2/managed-request.json`, `runtime-stdout.json`, `verification.json` |
| Gợi ý đo input token qua usage | Adapter API tùy chọn ghi usage nguyên bản | `llm.py`; lần bàn giao chưa có API usage thật |

Thiết kế vận dụng slide 18–26 (budget, checkpoint, selective compaction), slide
28–31 (Code Mode/runtime) và 34 (hai cơ chế bổ sung nhau).

## 2. Prompt và cách tự vận hành

Đã tạo `PROMPT_CHALLENGE_B.md` trước mã nguồn, đọc lại, rồi thực hiện ngay trong
phiên làm việc. Prompt có phân tích đề, thiết kế, kịch bản kiểm chứng và tiêu chí
hoàn tất. File prompt là đặc tả cho coding agent, không phải chương trình Python.

SHA-256 của prompt được lưu trong verification của mỗi lần demo:

```text
cf516ae9499b208c596ccc09baa847a59d5f9d5c36597cd371e26e899dd1ae23
```

Không tạo chat hoặc subagent. Đã xem mã và tài liệu Challenge A để tham khảo
cách tổ chức request, process lạnh, API adapter và bằng chứng. B không phụ thuộc
runtime/DB/server của A và không chỉnh sửa A.

## 3. B1: checkpoint phục vụ hành động tiếp theo

### Kịch bản điều tra thực sự

`fixtures/auth.py` có lỗi kiểm tra token bên ngoài lock. Hai thread dùng Barrier
để tái hiện interleaving có kiểm soát: cùng thấy token hợp lệ, rồi cùng rotate.
Regression test yêu cầu chỉ một request thành công; bản lỗi có hai success nên
FAIL, trong khi ba test tuần tự/replay/invalid token còn lại vẫn PASS.

Harness copy fixture sang workspace riêng rồi thực sự thay TTL từ 300 lên 3600,
chạy lại test; tiếp tục thay retry từ 0 lên 3 và chạy lại. Cả hai vẫn FAIL vì các
tham số này không thay đổi tính nguyên tử của check-and-consume. Log mỗi lần thử
được lưu. Đây là fixture học tập trong một process, không phải hệ thống auth
production hay bằng chứng về khóa phân tán.

Harness ghi các state event có nguồn nội bộ và tool results riêng. Để tạo bloat,
demo thêm tool output mô phỏng với payload dài và chỉ thị giả. Chỉ các lần chạy
regression và hai thử nghiệm được mô tả ở trên là tool test thật; các output
noise được tạo có chủ đích để kiểm tra quản lý context.

### Khi nào compact?

```text
input_limit = floor((window - output_reserve) * safety_ratio)
            = floor((32768 - 4096) * 0.70)
            = 20070 estimated tokens
```

Sau mỗi tool output, trước khi gửi request tiếp, harness đo request hoàn chỉnh.
Đạt ngưỡng thì compact; cũng hỗ trợ milestone và cold-start. Demo đạt ngưỡng sau
24 tool output, với 34 events tổng cộng. Đo token bằng bytes/4 là heuristic, nên
budget này không bảo đảm vừa context của mọi model; khi tích hợp thật cần dùng
tokenizer/count API phù hợp và xử lý output quá lớn ngay tại tool boundary.

### Giữ, nén, bỏ

- **KEEP:** goal, current state, mọi constraints, lỗi mở, findings đã xác nhận,
  failed attempts kèm kết quả, files và next_action.
- **TRUNCATE:** kết quả test chỉ cần lỗi chính, return code và vị trí evidence.
- **DROP khỏi active context:** raw tool output, payload dài và noise. History
  nguyên bản vẫn được archive trên đĩa và có SHA-256 để đối chiếu.

Reducer chỉ đọc state event có nguồn harness, không phân tích câu chữ trong log
để cập nhật state. Event mới thay current_state/next_action; issue resolved rời
danh sách open; failed attempts vẫn tồn tại. Trust boundary là harness phải tạo
state event đáng tin; metadata `source` không phải chữ ký chống người có quyền
sửa file. Nếu checkpoint không đủ trường hoặc vượt budget, compact bị từ chối,
không âm thầm bỏ constraints hay lỗi đang mở.

### Cold-start và kết quả

Harness tạo thư mục `cold-start` chỉ có checkpoint và bản copy code/test, rồi mở
Python process mới. Request agent nhận chứa system instructions, checkpoint và
task tiếp tục; không có transcript/log cũ. Archive không hiện diện trong thư mục
đó; worker không gọi đọc archive.

Agent demo đọc `next_action=inspect_lock`, kiểm tra validation nằm ngoài lock,
giữ nguyên API và chuyển validate/consume vào cùng critical section. Không thử
lại TTL/retry. Bản diff và log xác nhận **4/4 regression tests PASS**. Đây là
scripted repair có template đã kiểm tra, không phải LLM viết patch tự do. Demo
chứng minh checkpoint đủ cho hành động fixture đã định nghĩa và harness thực sự
tiếp tục chạy, không chứng minh chất lượng compact mọi hội thoại ngôn ngữ tự nhiên.

## 4. B2: xử lý trung gian trong runtime

### Câu hỏi và dữ liệu

Câu hỏi là tìm top 3 mã lỗi ERROR/FATAL trên mọi file, số lần, service liên quan,
thời điểm đầu/cuối và vị trí evidence. Không suy đoán root cause từ số lần xuất
hiện. Có 24 file JSONL, mỗi file 400 record hợp lệ và hai dòng hỏng: **9.648 dòng**.
Payload dài có raw canary và chỉ thị giả. Các trường payload/message luôn bị
bỏ khỏi aggregate, các chiều code/service phải qua kiểm tra định dạng.

Oracle độc lập sử dụng công thức sinh dữ liệu thay vì chạy lại thuật toán parse:
mỗi block 40 record có hai REFRESH_REUSE, một DB_TIMEOUT, một BAD_GATEWAY, một
WARN và 35 INFO. WARN không được tính vào lỗi. Có 10 block/file và 24 file.

### Luồng Code Mode

```text
Agent -> run_code(code)
      -> Python worker process
      -> tools.list_files + tools.read_lines
      -> parse, validate, count, group, rank, keep evidence locations
      -> one final JSON findings
      -> agent request -> answer
```

Program do coding agent viết và review trước, planner demo phát lại program
đó trong tool call; không tuyên bố có LLM sinh code vào thời điểm chạy demo.
Program thật sự được compile/execute trong worker. Code nhận SDK `tools`, đọc
25 tool calls nội bộ (1 list + 24 reads), và không print trong lúc xử lý. Runtime
chỉ in final JSON. Tool trace chỉ có metadata file/số dòng/bytes, không có raw
content. Agent chỉ nhận một kết quả aggregate.

Giới hạn: 128 file, 4 MB/file, 64 MB đọc tổng, 200.000 records, 8.192 bytes/dòng,
256 error codes, 64 services/code, output 12.000 bytes, timeout process 30s.
Đường dẫn được resolve và kiểm tra nằm trong root kể cả symlink/junction qua
resolve. Chương trình không trùng program đã duyệt bị từ chối. Các giới hạn này
hỗ trợ demo, không biến `exec` trong subprocess thành security sandbox; không
được mở runner này cho code không đáng tin trên máy production.

### Kết quả

| Mã lỗi | Số lần | auth | gateway | worker |
| --- | ---: | ---: | ---: | ---: |
| REFRESH_REUSE | 480 | 160 | 160 | 160 |
| BAD_GATEWAY | 240 | 80 | 80 | 80 |
| DB_TIMEOUT | 240 | 80 | 80 | 80 |

Có **960 ERROR/FATAL**, bỏ qua **48 dòng hỏng** (24 JSON sai, 24 thiếu schema).
BAD_GATEWAY đứng trước DB_TIMEOUT vì hòa số lần thì xếp code A–Z. Verifier kiểm
tra count/service/time range bằng oracle và mở lại file:line để xác nhận evidence.
Raw canary và chỉ thị giả không có trong managed request. Toàn bộ câu trả lời,
timestamp và evidence nằm trong `b2/answer.md` của lần chạy được chọn.

## 5. Số đo context và giới hạn kết luận

Lần bàn giao chuẩn: `output/demo/20261021T120236Z-17275980`, chạy lúc **19:02:36
ngày 21/10/2026 (UTC+7)**. Lần chạy mới nhất luôn được ghi trong `output/LATEST_DEMO.txt`.

| Phần | Request bytes trước | Request bytes sau | Giảm bytes | Token ước lượng trước | Token ước lượng sau |
| --- | ---: | ---: | ---: | ---: | ---: |
| B1 Compact | 81.447 | 2.405 | 97,047% | 20.362 | 602 |
| B2 Code Mode | 3.914.927 | 1.862 | 99,952% | 978.732 | 466 |

Đếm toàn request bằng JSON canonical UTF-8, cùng phương pháp trước/sau. Token
ước lượng là `ceil(bytes/4)`; không phải usage provider, token tính phí hay phần
trăm tiết kiệm chi phí. B2 baseline là request đối chứng offline chứa raw log,
không phải trace tích lũy của nhiều lượt native tool calling. Không gửi baseline
lớn đó tới API; chưa cộng overhead sinh code, tool definitions hay nhiều lượt
agent vào so sánh byte trên.

Lần triển khai chưa có OPENAI_API_KEY/OPENAI_MODEL nên **chưa gọi LLM thật** và
**chưa có usage.input_tokens thật**. Đã có adapter gọi OpenAI Responses API theo
[Text generation](https://developers.openai.com/api/docs/guides/text) và
[Counting tokens](https://developers.openai.com/api/docs/guides/token-counting).
Lệnh `python -B -X utf8 demo.py --with-api` sau khi cấu hình môi trường sẽ gửi
hai managed contexts, lưu output/usage thật và kiểm tra câu trả lời bằng oracle.
Không lưu key trong request artifact. Token API baseline vẫn không được đo;
không báo mức giảm usage thực tế khi chỉ có số đo request sau quản lý context.

## 6. Kiểm thử và bàn giao

**31/31 unittest PASS**, không có test skip, bằng chứng tại `output/tests.log`
và `output/tests-verification.json`. Ngoài ra fixture có 4 regression tests thật
được chạy nhiều lần để chứng minh test đỏ/trial vẫn đỏ/fix xanh. Verification
demo đạt **B1 8/8**, **B2 14/14**.

Nhóm kiểm tra gồm trigger/reserve, giữ/thay state, issue resolved, nguồn log giả,
checkpoint thiếu/hỏng/quá lớn, preserve state khi budget fail, cold process sửa
lỗi, aggregate trên dữ liệu nhỏ khác bộ demo, timezone, malformed records, count,
service, time ranges, evidence, path escape, file/line/records/byte/output limit,
timeout và từ chối code chưa duyệt. API adapter/evaluation dùng mock để kiểm tra
usage, raw exclusion, key không vào artifact, incomplete/error và câu trả lời sai
không được đánh dấu PASS. Mock không được tính là gọi LLM thật.

Đã chạy `run-demo.ps1` thành công: script kiểm thử trước rồi demo cả B1/B2.
README có hướng dẫn chạy, vị trí mã nguồn và cấu hình LLM tùy chọn. Nhật ký tại
`EXECUTION_LOG.md`; mỗi lần demo có báo cáo `REPORT.md`, verification JSON, request
trước/sau và code/log bằng chứng để người chấm xem lại.
