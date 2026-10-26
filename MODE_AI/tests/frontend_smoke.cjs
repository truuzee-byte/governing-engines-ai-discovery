const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1200,height:800}});
    await page.route('**/*',route=>route.request().url().startsWith('file:')?route.continue():route.abort());
    await page.goto(pathToFileURL(path.resolve('frontend/index.html')).href);
    assert.equal(await page.locator('nav button').count(),5);
    assert.match(await page.locator('#state').textContent(),/not connected/);
    const fixture={contract:'ModePresentation/1',source:'ACTIVE_RUNTIME_SNAPSHOT',execution_authority:false,
      state:'CLARIFYING',title:'Offline presentation fixture',thread_id:'fixture-thread',
      messages:[{role:'user',message_id:'1',content:'<img src=x onerror=alert(1)> Show the evidence first.'}],
      build:{state:'BUILD_PASS_RP_PENDING',reality:{accepted:false,rp_state:'PENDING_VALIDATION'}}};
    const load=async value=>page.locator('#snapshot').setInputFiles({name:'fixture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
    await load(fixture);
    await page.getByText('CLARIFYING · captured',{exact:true}).waitFor();
    assert.equal(await page.locator('#messages img').count(),0);
    await page.getByRole('button',{name:'Build Mode',exact:true}).click();
    assert.match(await page.locator('#panel').textContent(),/PENDING_VALIDATION/);
    await page.getByRole('button',{name:'Chat Mode',exact:true}).click();
    await page.screenshot({path:'artifacts/frontend-preparation.png',fullPage:true});
    await load({...fixture,state:'FAKE_PASS'});
    await page.getByText('Snapshot unavailable',{exact:true}).waitFor();
    assert.equal(await page.locator('#messages article').count(),0);
    assert.equal(await page.locator('#thread').textContent(),'');
    console.log('FRONTEND_SMOKE_PASSED — offline fixture only');
  } finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
