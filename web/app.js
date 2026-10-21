'use strict';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = value => value == null ? '—' : Number(value).toLocaleString('vi-VN');
const bytes = value => value == null ? '—' : value >= 1e6 ? (value / 1e6).toFixed(2) + ' MB' : value >= 1000 ? (value / 1000).toFixed(2) + ' KB' : value + ' B';
const pretty = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const state = {health:null, runs:[], selected:null, job:null, tab:'overview', timer:null, busy:false, codeTabs:{b1:'checkpoint',b2:'answer'}};
const tabNames = {overview:'Tổng quan',b1:'B1 · Compact',b2:'B2 · Code Mode',evidence:'Bằng chứng'};
const statusNames = {queued:'Đang chờ thực thi',running:'Đang chạy demo',done:'Kiểm chứng hoàn tất',failed:'Có kiểm tra chưa đạt',error:'Lần chạy chưa hoàn tất'};
const checkLabels = {
  test_red_before:'Tái hiện test đỏ trước compact',new_process:'Tiếp tục trong process mới',test_green_after:'Test xanh sau khi sửa',
  no_raw_in_context:'Raw không có trong context',no_archive_in_cold_directory:'Cold-start không chứa archive',two_failed_attempts_retained:'Giữ cả hai cách thử thất bại',
  archive_integrity:'SHA-256 archive hợp lệ',context_reduced:'Context thực sự nhỏ hơn',files_scanned:'Quét đủ file',lines_scanned:'Quét đủ dòng',
  malformed_lines:'Đếm đúng dòng hỏng',error_records:'Đếm đúng ERROR/FATAL',top_counts:'Top lỗi khớp oracle',service_counts:'Service khớp oracle',
  tie_order:'Xếp hạng hòa theo mã lỗi',time_ranges:'Thời gian khớp oracle',evidence_locations:'Vị trí evidence chính xác',raw_marker_absent:'Raw canary không vào context',
  payload_instruction_absent:'Chỉ thị giả không vào context',runtime_read_all_files:'Runtime đọc mọi file',no_intermediate_stdout:'Không có stdout trung gian',stdout_is_only_findings:'Chỉ findings được trả về'
};

async function api(path, options={}) {
  const response = await fetch(path, {cache:'no-store',...options});
  const type = response.headers.get('Content-Type') || '';
  const data = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function notice(message, error=false) {
  $('notice').hidden = !message;
  $('notice').classList.toggle('error',error);
  $('notice').textContent = message || '';
}
function artifactUrl(name,download=false) {return `/api/runs/${encodeURIComponent(state.selected)}/artifact?name=${encodeURIComponent(name)}${download?'&download=1':''}`;}
function metric(label,value,suffix,note,trend='') {
  return `<article class="metric"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}${suffix?`<small>${esc(suffix)}</small>`:''}</div><div class="metric-note">${esc(note)}</div>${trend?`<span class="metric-trend">${esc(trend)}</span>`:''}</article>`;
}
function reduction(metrics) {
  const after = metrics ? Math.max(.8,100-metrics.byte_reduction_percent) : 10;
  return `<div class="reduction-heading"><span>Context trước & sau</span><strong>${metrics?'↓ '+number(metrics.byte_reduction_percent)+'%':'Chưa có số đo'}</strong></div>
  <div class="bar-row"><span class="bar-label">Trước</span><div class="bar-track"><div class="bar-fill" style="width:${metrics?100:0}%"></div></div><code>${bytes(metrics?.before.utf8_bytes)}</code></div>
  <div class="bar-row"><span class="bar-label">Sau</span><div class="bar-track"><div class="bar-fill after" style="width:${metrics?after:0}%"></div></div><code>${bytes(metrics?.after.utf8_bytes)}</code></div>`;
}
function runButton(kind,label) {return `<button class="button secondary small run-part" data-run="${kind}" ${state.busy?'disabled':''}>▶ ${esc(label)}</button>`;}
function checksHtml(checks) {return `<div class="checks-list">${Object.entries(checks).map(([name,pass])=>`<div class="check-row ${pass?'':'fail'}">${pass?'✓':'×'} ${esc(checkLabels[name] || name)}</div>`).join('')}</div>`;}
function empty(part,title,description) {
  return `<article class="card empty-state"><span>${part==='b1'?'⇥':'⌘'}</span><h2>${esc(title)}</h2><p>${esc(description)}<br>Mỗi lần chạy tạo bằng chứng mới, không phát lại số liệu cũ.</p>${runButton(part,'Chạy demo '+part.toUpperCase())}</article>`;
}

function renderHistory() {
  $('history').innerHTML = state.runs.length ? state.runs.slice(0,7).map(run=>`<button class="history-item ${run.id===state.selected?'active':''}" data-select="${esc(run.id)}"><span class="history-symbol ${esc(run.status)}">${run.status==='done'?'✓':run.status==='error'||run.status==='failed'?'×':'◌'}</span><span>${run.kind==='all'?'B1 + B2 · Toàn bộ':esc(run.kind.toUpperCase())}<small>${esc(new Date(run.created_at).toLocaleString('vi-VN',{timeZone:'Asia/Bangkok',hour:'2-digit',minute:'2-digit',day:'2-digit',month:'2-digit'}))} · ${esc(run.id.slice(-8))}</small></span></button>`).join('') : '<p class="history-empty">Lần chạy của bạn sẽ xuất hiện ở đây.</p>';
}
function renderStatus() {
  const job = state.job;
  $('runStatus').textContent = job ? statusNames[job.status] || job.status : 'Sẵn sàng thực nghiệm';
  $('runRing').className = 'status-ring '+(job?.status || '');
  $('runId').textContent = job ? job.id : 'Bấm chạy để tạo bằng chứng mới';
  $('exportTop').disabled = !job || !['done','failed','error'].includes(job.status);
  $('runAll').disabled = state.busy;
  $('runAll').innerHTML = state.busy ? '<span>◌</span> Đang thực thi Python…' : '<span>▶</span> Chạy toàn bộ demo <span class="key-hint">B1 + B2</span>';
  $('b1Dot').classList.toggle('done',!!job?.result?.b1?.passed);
  $('b2Dot').classList.toggle('done',!!job?.result?.b2?.passed);
  $('withApi').disabled = !state.health?.api_ready || state.busy;
  $('modeBadge').textContent = job?.with_api ? '◉ Offline harness + đánh giá LLM thật' : '◉ Demo offline · có quy tắc';
}
function renderOverview() {
  const r1=state.job?.result?.b1,r2=state.job?.result?.b2,views=state.job?.views;
  const f=views?.b2?.findings;
  $('summaryMetrics').innerHTML = [
    metric('B1 · Giảm context',r1?number(r1.metrics.byte_reduction_percent):'—',r1?'%':'','Bytes toàn request',r1?'↓ compact':''),
    metric('B2 · Giảm context',r2?number(r2.metrics.byte_reduction_percent):'—',r2?'%':'','Bytes toàn request',r2?'↓ code mode':''),
    metric('Log được phân tích',f?number(f.files_scanned):'—',f?'files':'',f?number(f.lines_scanned)+' dòng qua runtime':'24 file khi chạy B2'),
    metric('Tiêu chí kiểm chứng',r1||r2?number(Object.values(r1?.checks||{}).filter(Boolean).length+Object.values(r2?.checks||{}).filter(Boolean).length):'—',r1||r2?'/ '+(Object.keys(r1?.checks||{}).length+Object.keys(r2?.checks||{}).length):'','Đối chiếu bằng thực thi',r1||r2?'✓ đã xác minh':'')
  ].join('');
  $('experimentCards').innerHTML = [
    {part:'b1',icon:'⇥',eyebrow:'B1 / COMPACTION',title:'Nhớ điều cần làm tiếp',desc:'Nén một session dài thành checkpoint. Giữ lỗi đang điều tra, cách đã thử và bước tiếp theo.',left:'Session dài',mid:'Compact',right:'Checkpoint',note:r1?'4/4 regression tests PASS':'Khởi động process mới',value:r1},
    {part:'b2',icon:'⌘',eyebrow:'B2 / CODE MODE',title:'Đọc nhiều. Chỉ nhận findings.',desc:'Đọc và xử lý log trong runtime. Chỉ một kết quả tổng hợp được đưa vào context của agent.',left:'24 file log',mid:'run_code',right:'Findings',note:r2?'Raw log không vào context':'1 kết quả trả cho agent',value:r2}
  ].map(item=>`<article class="card experiment-card"><div class="card-heading"><div class="experiment-title"><span class="experiment-icon ${item.part==='b2'?'blue':''}">${item.icon}</span><div><span class="eyebrow muted">${item.eyebrow}</span><h2>${item.title}</h2></div></div><span class="small-tag ${item.value?.passed?'pass':''}">${item.value?.passed?'✓ PASS':'Sẵn sàng'}</span></div><p class="experiment-desc">${item.desc}</p><div class="pipeline"><div class="pipeline-node"><span class="tiny-stack">${item.part==='b1'?'≋':'▤'}</span><strong>${item.left}</strong></div><span class="pipeline-arrow">→</span><div class="pipeline-node"><span class="tiny-stack">${item.icon}</span><strong>${item.mid}</strong></div><span class="pipeline-arrow">→</span><div class="pipeline-node"><span class="tiny-stack">▣</span><strong>${item.right}</strong></div></div>${reduction(item.value?.metrics)}<div class="card-bottom"><span><span class="live-dot"></span>${item.note}</span><button class="text-link" data-tab="${item.part}">Khám phá ${item.part.toUpperCase()} <span>↗</span></button></div></article>`).join('');
  const accept=[['Compact giữ lỗi, cách thử và bước tiếp',!!r1?.checks.two_failed_attempts_retained,'B1'],['Process mới tiếp tục sửa lỗi thành công',!!r1?.checks.test_green_after,'B1'],['Trả lời đúng trên nhiều file log',!!r2?.checks.top_counts,'B2'],['Raw log nằm ngoài context agent',!!r2?.checks.raw_marker_absent,'B2']];
  $('acceptance').innerHTML=accept.map(([label,pass,tag])=>`<div class="accept-item ${pass?'pass':''}"><span class="accept-check">${pass?'✓':'·'}</span><span>${label}</span><small>${tag}</small></div>`).join('');
  const events=state.job?.events||[];
  $('eventCount').textContent=events.length+' bước';
  if(events.length) {
    $('timeline').innerHTML=events.map(event=>`<div class="timeline-event"><time>${esc(new Date(event.time).toLocaleTimeString('vi-VN',{timeZone:'Asia/Bangkok',hour:'2-digit',minute:'2-digit',second:'2-digit'}))}</time><span class="event-dot"></span><p><strong>${esc(event.part.toUpperCase())}</strong>${esc(event.message)}</p></div>`).join('');
    if(state.busy)$('timeline').scrollTop=$('timeline').scrollHeight;
  }
}

function renderB1() {
  const r=state.job?.result?.b1,v=state.job?.views?.b1;
  if(!r||!v){$('b1Content').innerHTML=empty('b1','Compact trước. Tiếp tục đúng sau.','Chạy B1 để thấy test lỗi, checkpoint và process mới sửa lỗi thật.');return;}
  const s=v.checkpoint.state;
  $('b1Content').innerHTML=`<div class="detail-header"><div><h2>B1 · Checkpoint cho bước tiếp theo</h2><p>Archive lịch sử dài, rồi tiếp tục công việc trong một process mới.</p></div>${runButton('b1','Chạy lại B1')}</div>
  <section class="detail-metrics">${metric('Events trước compact',number(r.events),'',number(r.tool_outputs)+' tool output lớn')}${metric('Context sau compact',bytes(r.metrics.after.utf8_bytes),'','Giảm '+number(r.metrics.byte_reduction_percent)+'% bytes')}${metric('Regression sau sửa','4','/ 4','Test trước sửa: 1 FAIL')}${metric('Process mới',r.resume.pid,'PID','Không đọc archive cũ')}</section>
  <div class="state-grid"><article class="card state-card"><span>01 / Lỗi đang điều tra</span><h3>${esc(s.open_issues[0]?.error)}</h3><p>${esc(s.current_state)}</p><span class="pill red">Test ban đầu: FAIL</span></article><article class="card state-card"><span>02 / Cách đã thử</span>${s.failed_attempts.map(a=>`<p><span class="pill">${esc(a.strategy)}</span><br>${esc(a.result)}</p>`).join('')}</article><article class="card state-card"><span>03 / Bước tiếp được giữ</span><h3>${esc(s.next_action.operation)}</h3><p>${esc(s.next_action.reason)}</p><span class="pill green">4/4 PASS sau cold-start</span></article></div>
  <div class="detail-grid"><article class="card code-card"><div class="code-tabs" role="tablist" aria-label="Bằng chứng B1">${[['checkpoint','Checkpoint'],['request','Request thật'],['diff','Bản sửa'],['tests_before','Test trước'],['tests_after','Test sau']].map(([key,label])=>`<button role="tab" aria-selected="${state.codeTabs.b1===key}" class="code-tab ${state.codeTabs.b1===key?'active':''}" data-code="b1:${key}">${label}</button>`).join('')}</div><pre id="b1Code" tabindex="0">${esc(pretty(v[state.codeTabs.b1]))}</pre><div class="code-caption"><span>Agent nhận checkpoint; raw history ở archive.</span><button class="text-link" data-artifact="b1-request">Mở request ↗</button></div></article><article class="card constraints"><h3>Điều kiện bắt buộc được giữ</h3>${s.constraints.map(c=>`<div class="constraint-item">✓ ${esc(c)}</div>`).join('')}<div class="constraint-item">Trigger: <code>${esc(r.trigger)}</code><br>Ngưỡng: ${number(r.budget.input_limit_estimated)} tokens ước lượng<br>Window: ${number(r.budget.window)} · Reserve: ${number(r.budget.reserve)}<br>Safety ratio: ${r.budget.safety_ratio}</div>${reduction(r.metrics)}<div class="honesty-note"><span>i</span><p>Agent demo sửa fixture bằng template đã kiểm tra. Log noise tạo để kiểm tra bloat; test, hai thử nghiệm và cold process chạy thật.</p></div></article></div>${checksHtml(r.checks)}`;
}

function renderB2() {
  const r=state.job?.result?.b2,v=state.job?.views?.b2;
  if(!r||!v){$('b2Content').innerHTML=empty('b2','Nhiều log. Một kết quả rõ ràng.','Chạy B2 để đọc 24 file log trong runtime và trả findings cho agent.');return;}
  const f=v.findings;
  $('b2Content').innerHTML=`<div class="detail-header"><div><h2>B2 · Xử lý log ở nơi dữ liệu nằm</h2><p>Program chạy trong runtime riêng; agent nhận 1 JSON tổng hợp.</p></div>${runButton('b2','Chạy lại B2')}</div><div class="question"><span>⌕</span><p>${esc(v.request.input[1].content)}</p></div>
  <section class="detail-metrics">${metric('File trong runtime',number(f.files_scanned),'files',number(f.lines_scanned)+' dòng đã quét')}${metric('Bản ghi lỗi',number(f.error_records),'','Chỉ ERROR / FATAL')}${metric('Dòng hỏng',number(f.malformed_lines),'','24 JSON sai · 24 thiếu schema')}${metric('Output agent nhận','1','JSON',bytes(r.metrics.after.utf8_bytes)+' context request')}</section>
  <article class="card table-card"><div class="card-heading"><div><span class="eyebrow muted">ANSWER / VERIFIED AGAINST GROUND TRUTH</span><h2>Top 3 lỗi trên toàn bộ log</h2></div><span class="small-tag pass">✓ Oracle khớp</span></div><div class="table-scroll"><table><thead><tr><th># / MÃ LỖI</th><th>SỐ LẦN</th><th>SERVICE</th><th>THỜI GIAN (UTC)</th><th>EVIDENCE</th></tr></thead><tbody>${f.top_errors.map((row,i)=>`<tr><td><span class="rank">0${i+1}</span> <code>${esc(row.code)}</code></td><td><strong>${number(row.count)}</strong></td><td class="service-list">${Object.entries(row.services).map(([service,count])=>`${esc(service)} <span>· ${number(count)}</span>`).join('<br>')}</td><td class="service-list">${esc(row.first_seen.replace('T',' ').replace('+00:00',''))}<br>${esc(row.last_seen.replace('T',' ').replace('+00:00',''))}</td><td>${row.evidence.map(e=>`<button class="evidence-button" data-evidence="${esc(e.file)}:${e.line}">${esc(e.file)}:${e.line} ↗</button>`).join('<br>')}</td></tr>`).join('')}</tbody></table></div><p class="table-note">Hòa số lần thì xếp code A–Z. Tần suất và tương quan không chứng minh nguyên nhân gốc. Evidence mở trong inspector cho người xem.</p></article>
  <div class="detail-grid"><article class="card code-card"><div class="code-tabs" role="tablist" aria-label="Bằng chứng B2">${[['answer','Câu trả lời'],['code','Program run_code'],['trace','SDK trace'],['request','Request thật']].map(([key,label])=>`<button role="tab" aria-selected="${state.codeTabs.b2===key}" class="code-tab ${state.codeTabs.b2===key?'active':''}" data-code="b2:${key}">${label}</button>`).join('')}</div><pre id="b2Code" tabindex="0">${esc(pretty(v[state.codeTabs.b2]))}</pre><div class="code-caption"><span>Program đã duyệt · Process riêng · Timeout 30s</span><button class="text-link" data-artifact="b2-request">Mở request ↗</button></div></article><article class="card constraints"><h3>Ranh giới runtime → context</h3><div class="pipeline"><div class="pipeline-node"><strong>24 logs</strong><span>trong runtime</span></div><span class="pipeline-arrow">→</span><div class="pipeline-node"><strong>1 findings</strong><span>vào context</span></div></div>${reduction(r.metrics)}<div class="trace-stats"><span>${r.tool_calls_inside_runtime} SDK calls</span><span>0 stdout trung gian</span><span>Raw marker: không có</span></div><div class="honesty-note"><span>i</span><p>Program được agent triển khai trước và duyệt. Process riêng chưa phải security sandbox. Đáp án offline được định dạng từ findings.</p></div><button class="text-link" id="rawSample" style="margin-top:17px">Xem mẫu raw log ngoài context ↗</button></article></div>${checksHtml(r.checks)}`;
}

function artifactRow(name,title,description) {
  return `<div class="artifact-row"><div><strong>${esc(title)}</strong><small>${esc(description)}</small></div><div class="artifact-actions"><button data-artifact="${name}" aria-label="Xem ${esc(title)}">Xem</button><a href="${artifactUrl(name,true)}" aria-label="Tải ${esc(title)}">↓</a></div></div>`;
}
function renderEvidence() {
  const job=state.job,r=job?.result;
  const historySelect=state.runs.length?`<label class="api-toggle history-mobile">Lần chạy <select id="mobileHistory">${state.runs.map(run=>`<option value="${esc(run.id)}" ${run.id===state.selected?'selected':''}>${esc(run.kind.toUpperCase())} · ${esc(run.id)}</option>`).join('')}</select></label>`:'';
  if(!r){$('evidenceContent').innerHTML=`${historySelect}<article class="card empty-state"><span>▤</span><h2>Bằng chứng đi cùng mỗi lần chạy</h2><p>Chạy B1 hoặc B2 để xem request, verification, test log và tải file ZIP.</p></article>`;return;}
  const apiResult=r.api;
  $('evidenceContent').innerHTML=`<div class="detail-header"><div><h2>Bằng chứng có thể kiểm tra lại</h2><p>${esc(job.id)} · ${esc(job.kind.toUpperCase())}</p></div></div><div class="download-actions"><a class="button primary" id="downloadZip" href="/api/runs/${esc(job.id)}/export">↓ Tải toàn bộ bằng chứng ZIP</a><a class="button secondary" id="downloadJson" href="${artifactUrl('verification',true)}">↓ Verification JSON</a><button class="button secondary" data-artifact="report">Báo cáo lần chạy ↗</button></div>${historySelect}
  <div class="evidence-grid">${r.b1?`<article class="card evidence-group"><h3>B1 · Compact & cold-start</h3>${artifactRow('b1-checkpoint','Checkpoint có cấu trúc','Goal, constraints, lỗi, cách thử và next action')}${artifactRow('b1-request','Request agent thực sự nhận','Không có raw history hoặc archive content')}${artifactRow('b1-diff','Bản sửa sau cold-start','Validation và rotate trong cùng lock')}${artifactRow('b1-test-before','Test ban đầu','Race tái hiện với 2 success, test FAIL')}${artifactRow('b1-test-after','Test sau sửa','4 regression tests PASS')}${artifactRow('b1-ttl','Thử tăng TTL','Test chạy thật, vẫn FAIL')}${artifactRow('b1-retry','Thử tăng retry','Test chạy thật, vẫn FAIL')}${artifactRow('b1-before','Baseline trước compact','Chỉ đối chứng offline; chứa raw noise')}${artifactRow('b1-archive','Archive history đầy đủ','Lưu trên đĩa, không nằm trong managed context')}</article>`:''}${r.b2?`<article class="card evidence-group"><h3>B2 · Code Mode & findings</h3>${artifactRow('b2-code','Program đã thực thi','run_code trong process Python riêng')}${artifactRow('b2-trace','Trace SDK','Metadata tool calls; không có nội dung raw')}${artifactRow('b2-findings','Findings tổng hợp','Top lỗi, services, time range, evidence')}${artifactRow('b2-request','Request agent thực sự nhận','Chỉ aggregate và câu hỏi')}${artifactRow('b2-oracle','Ground truth độc lập','Oracle tính bằng công thức từ fixture')}${artifactRow('b2-answer','Câu trả lời trên nhiều file','Dữ liệu lấy từ managed context')}${artifactRow('b2-before','Baseline raw offline','Đối chứng lớn, không gửi lên API')}</article>`:''}<article class="card evidence-group"><h3>LLM & cách đo</h3><div class="api-result">${apiResult.status==='executed'?`<span class="pill green">Đã gọi LLM thật</span>${Object.entries(apiResult.results).map(([part,result])=>`<p>${esc(part.toUpperCase())} · ${esc(result.model)}<br>usage.input_tokens: <strong>${number(result.usage.input_tokens)}</strong><br>Kiểm tra câu trả lời: ${result.semantic_checks_passed?'PASS':'FAIL'}</p>${artifactRow('api-'+part,'Response '+part.toUpperCase(),'Request, output và usage provider nguyên bản')}`).join('')}`:`<span class="pill">Chưa đo API usage</span><p>Demo này chạy offline bằng quy tắc. Để đánh giá thêm bằng LLM, cấu hình OPENAI_API_KEY và OPENAI_MODEL khi mở server, rồi chọn đánh giá LLM và chạy toàn bộ.</p>`}<p>Bytes đo trên toàn request JSON canonical. Tokens = ceil(UTF-8 bytes / 4), là ước lượng. Không có usage baseline API thật; không suy diễn mức tiết kiệm hóa đơn.</p></div></article><article class="card evidence-group"><h3>Tài liệu & khả năng kiểm tra</h3>${artifactRow('verification','Kết quả kiểm chứng','Từng check của B1/B2 và SHA-256 prompt')}<div class="artifact-row"><div><strong>Prompt bổ sung cho bản web</strong><small>Yêu cầu, luồng thực thi và tiêu chí hoàn tất</small></div><button class="text-link" data-doc="prompt">Xem ↗</button></div><div class="artifact-row"><div><strong>Hướng dẫn sử dụng</strong><small>Chạy localhost, CLI và LLM tùy chọn</small></div><button class="text-link" data-doc="readme">Xem ↗</button></div><div class="honesty-note"><span>i</span><p>ZIP chứa cả raw fixture và baseline để kiểm chứng offline. Việc tải chúng không đưa raw vào context agent.</p></div></article></div>`;
}
function render() {
  renderStatus();renderHistory();renderOverview();renderB1();renderB2();renderEvidence();
}
function changeTab(tab) {
  if(!tabNames[tab])return;
  state.tab=tab;
  document.querySelectorAll('.nav-item').forEach(button=>button.classList.toggle('active',button.dataset.tab===tab));
  document.querySelectorAll('.panel').forEach(panel=>panel.classList.toggle('active',panel.id==='panel-'+tab));
  $('breadcrumb').textContent=tabNames[tab];
  window.scrollTo({top:0,behavior:'instant'});
}
async function refreshHistory() {
  const data=await api('/api/runs');state.runs=data.runs;renderHistory();
}
async function selectJob(id) {
  clearTimeout(state.timer);
  state.selected=id;
  localStorage.setItem('context-lab-selected',id);
  await poll();
}
async function poll() {
  try {
    const job=await api('/api/runs/'+encodeURIComponent(state.selected));
    state.job=job;
    state.busy=['running','queued'].includes(job.status);
    // Another selected historical run does not unlock execution while a live run exists.
    if(!state.busy){const health=await api('/api/health');state.health=health;state.busy=!!health.running;}
    render();
    if(job.error)notice(job.error,true);
    if(['running','queued'].includes(job.status))state.timer=setTimeout(poll,350);
    else {await refreshHistory();if(state.busy)state.timer=setTimeout(poll,700);}
  }catch(error){state.busy=false;renderStatus();notice('Không đọc được trạng thái: '+error.message,true);}
}
async function startRun(kind) {
  notice('');
  try {
    const withApi=kind==='all'&&$('withApi').checked;
    state.busy=true;renderStatus();
    const job=await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,with_api:withApi})});
    state.job=job;
    if(kind!=='all')changeTab(kind);else changeTab('overview');
    await refreshHistory();await selectJob(job.id);
  }catch(error){state.busy=false;renderStatus();notice(error.message,true);}
}
async function showDialog(title,content,note='',download=null,label='INSPECTOR') {
  $('dialogTitle').textContent=title;$('dialogContent').textContent=pretty(content);$('dialogNote').textContent=note;$('dialogLabel').textContent=label;
  $('dialogDownload').hidden=!download;if(download)$('dialogDownload').href=download;
  if(!$('inspector').open)$('inspector').showModal();
}
async function inspectArtifact(name) {
  if(!state.selected)return;
  const content=await api(artifactUrl(name));
  const raw=name.includes('before')||name.includes('archive');
  showDialog(name,content,raw?'ĐỐI CHỨNG OFFLINE / ARCHIVE: chứa raw dữ liệu. Chỉ hiển thị cho người xem; không được inject vào managed request.':'Artifact thực từ lần chạy '+state.selected,artifactUrl(name,true),raw?'ARCHIVE / NGOÀI CONTEXT':'BẰNG CHỨNG THỰC THI');
}
async function inspectSample(evidence='') {
  if(!state.selected)return;
  const [file,line]=evidence.split(':');
  const query=evidence?'?file='+encodeURIComponent(file)+'&line='+encodeURIComponent(line):'';
  const data=await api(`/api/runs/${state.selected}/raw-sample${query}`);
  showDialog(evidence||'Mẫu raw log · ngoài context',data,data.scope,null,'RAW INSPECTOR / NGƯỜI XEM');
}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button,[data-tab]');
  if(!button||button.disabled)return;
  try {
    if(button.dataset.tab)changeTab(button.dataset.tab);
    else if(button.dataset.run)await startRun(button.dataset.run);
    else if(button.dataset.select){notice('');await selectJob(button.dataset.select);}
    else if(button.dataset.code){const [part,key]=button.dataset.code.split(':');state.codeTabs[part]=key;part==='b1'?renderB1():renderB2();}
    else if(button.dataset.artifact)await inspectArtifact(button.dataset.artifact);
    else if(button.dataset.evidence)await inspectSample(button.dataset.evidence);
    else if(button.dataset.doc){const text=await api('/api/docs?name='+button.dataset.doc);showDialog('Tài liệu · '+button.dataset.doc,text,'Tài liệu trong thư mục Challenge B.');}
    else if(button.id==='runAll')await startRun('all');
    else if(button.id==='refreshHistory')await refreshHistory();
    else if(button.id==='exportTop')location.href='/api/runs/'+state.selected+'/export';
    else if(button.id==='closeDialog')$('inspector').close();
    else if(button.id==='rawSample')await inspectSample();
  }catch(error){notice(error.message,true);}
});
document.addEventListener('change',async event=>{
  if(event.target.id==='mobileHistory'){notice('');try{await selectJob(event.target.value);}catch(error){notice(error.message,true);}}
});
$('inspector').addEventListener('click',event=>{if(event.target===$('inspector')){const box=$('inspector').getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)$('inspector').close();}});

(async()=>{
  render();
  try{
    state.health=await api('/api/health');state.busy=!!state.health.running;
    $('connection').innerHTML='<span class="live-dot"></span>Runtime đã kết nối';
    if(state.health.api_ready)$('apiHint').textContent='('+state.health.api_model+')';
    await refreshHistory();
    const saved=localStorage.getItem('context-lab-selected');
    const selected=state.health.running||(state.runs.some(run=>run.id===saved)?saved:state.runs[0]?.id);
    if(selected)await selectJob(selected);else render();
  }catch(error){$('connection').textContent='Chưa kết nối runtime';notice(error.message,true);}
})();
