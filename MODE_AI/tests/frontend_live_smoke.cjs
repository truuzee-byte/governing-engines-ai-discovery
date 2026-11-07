const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);
  if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();
    await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);
    await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    assert.match(await page.locator('#messages').textContent(),/local only/);
    assert.equal(new URL(page.url()).hash,'');
    assert.equal(await page.locator('#snapshot').isDisabled(),true);
    await page.route('**/history',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({
      contract:'ModeHistory/1',execution_authority:false,
      threads:{state:'RETRIEVED',items:[{title:'Retrieved thread',thread_id:'fixture-thread'}]},
      past_builds:{state:'RETRIEVED',items:[]}})}));
    await page.getByRole('button',{name:'Chat Threads',exact:true}).click();
    await page.locator('#panel article').filter({hasText:'Retrieved thread · fixture-thread'}).waitFor();
    await page.route('**/thread?*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({
      contract:'ModeThreadView/1',thread_id:'fixture-thread',title:'Retrieved thread',execution_authority:false,
      messages:[{role:'user',content:'Preserved conversation words.'}]})}));
    await page.getByRole('button',{name:'Read conversation',exact:true}).click();
    await page.getByText('user: Preserved conversation words.',{exact:true}).waitFor();
    await page.route('**/state',r=>r.fulfill({status:403,body:'Denied'}));
    await page.getByText('Runtime unavailable',{exact:true}).waitFor();
    assert.equal(await page.locator('#panel').textContent(),'');
    console.log('LIVE_LOCAL_VIEW_BINDING_PASSED — synthetic runtime only');
  }finally{await browser.close();}
})().catch(()=>{console.error('Live local view binding failed');process.exitCode=1;});
