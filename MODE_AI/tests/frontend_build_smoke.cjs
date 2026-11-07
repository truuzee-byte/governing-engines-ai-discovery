const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);
  if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Build Mode',exact:true}).click();
    await page.getByLabel('Governed build request JSON',{exact:true}).fill(process.env.MODE_BUILD_FIXTURE);
    await page.getByRole('button',{name:'Submit governed build request',exact:true}).click();
    await page.getByText('Build request queued for canonical runtime validation. No execution or success inferred.',{exact:true}).waitFor();
  }finally{await browser.close();}
})().catch(()=>{console.error('Governed build UI fixture failed');process.exitCode=1;});
