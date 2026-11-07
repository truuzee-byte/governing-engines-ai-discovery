const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);
  if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();
    await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    if(process.env.MODE_CONTROL_TEST==='onboarding'){
      await page.getByRole('button',{name:'Operator Onboarding',exact:true}).click();
      await page.getByLabel('Preferred name',{exact:true}).fill('Chosen from UI');
      await page.getByRole('button',{name:'Save Operator answers',exact:true}).click();
      await page.getByText('Answers queued. Waiting for runtime acceptance.',{exact:true}).waitFor();
    }else{
      await page.getByText('Exact proposed memory.',{exact:true}).waitFor();
      await page.getByRole('button',{name:'Session only',exact:true}).click();
      await page.getByText('Choice queued for this memory proposal.',{exact:true}).waitFor();
    }
    console.log('SCOPED_CONTROL_QUEUED');
  }finally{await browser.close();}
})().catch(()=>{console.error('Scoped control browser fixture failed');process.exitCode=1;});
