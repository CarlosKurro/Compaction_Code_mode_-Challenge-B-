// Run one demonstration on an already running, user-facing Context Lab server.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname,'..');
const url = process.env.CONTEXT_LIVE_URL || 'http://127.0.0.1:8766';
(async()=>{
  const executable=['C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe','C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'].find(fs.existsSync);
  const browser=await chromium.launch({headless:true,executablePath:executable});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1050}});
    const health=await (await page.request.get(url+'/api/health')).json();
    assert.equal(health.app,'challenge-b-context-lab');
    assert(!health.running,'A run is already active; do not interrupt it.');
    await page.goto(url,{waitUntil:'networkidle'});
    await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('đã kết nối'));
    const previousId=await page.locator('#runId').innerText();
    await page.locator('#runAll').click();
    await page.waitForFunction(old=>document.getElementById('runId').textContent!==old&&['Kiểm chứng hoàn tất','Lần chạy chưa hoàn tất','Có kiểm tra chưa đạt'].includes(document.getElementById('runStatus').textContent),previousId,{timeout:30000});
    const runId=await page.locator('#runId').innerText();
    const job=await (await page.request.get(url+'/api/runs/'+runId)).json();
    assert(job.result?.passed && job.result.b1.passed && job.result.b2.passed,JSON.stringify({status:job.status,error:job.error}));
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:path.join(root,'output/web-qa/08-live-demo.png'),fullPage:true});
    fs.writeFileSync(path.join(root,'output/web-qa/live-verification.json'),JSON.stringify({
      url,run_id:runId,passed:true,b1_checks:job.result.b1.checks,b2_checks:job.result.b2.checks,
      real_llm_called:false,verified_at:new Date().toISOString(),note:'Clicked Run all in the live application. Server kept running for the user.'
    },null,2));
    console.log('Live demo PASS: '+url+' · '+runId);
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
