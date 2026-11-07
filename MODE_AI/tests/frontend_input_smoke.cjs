const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);
  if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1200,height:900}});
    await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);
    await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    assert.equal(await page.locator('#operator-form').isVisible(),true);
    await page.locator('#operator-text').fill('A queued fixture message.');
    await page.getByRole('button',{name:'Send to Mode',exact:true}).click();
    await page.getByText('Queued for the normal runtime. No execution approval inferred.',{exact:true}).waitFor();
    assert.equal(await page.locator('#operator-text').inputValue(),'');
    await page.screenshot({path:'artifacts/frontend-operator-input.png',fullPage:true});
    console.log('OPERATOR_INPUT_BROWSER_PASSED');
  }finally{await browser.close();}
})().catch(()=>{console.error('Operator input browser fixture failed');process.exitCode=1;});
