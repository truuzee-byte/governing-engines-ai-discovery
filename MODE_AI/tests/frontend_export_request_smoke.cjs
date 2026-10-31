const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);
    await page.getByRole('combobox',{name:'Document export format'}).selectOption('HTML');
    await page.getByRole('button',{name:'Prepare document export',exact:true}).click();
    await page.getByText('Exact document export queued. Download becomes available when serialization completes.',{exact:true}).waitFor();
  }finally{await browser.close();}
})().catch(()=>{console.error('Export request fixture failed');process.exitCode=1;});
