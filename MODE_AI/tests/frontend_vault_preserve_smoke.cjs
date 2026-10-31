const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Chat Threads',exact:true}).click();
    await page.getByRole('button',{name:'Read conversation',exact:true}).click();
    await page.getByLabel('Vault project ID',{exact:true}).fill('project');
    await page.getByRole('button',{name:'Preserve this stored version in Vault',exact:true}).click();
    await page.getByText('Exact stored-thread preservation queued. Wait for the Vault custody reference.',{exact:true}).waitFor();
  }finally{await browser.close();}
})().catch(()=>{console.error('Vault preservation fixture failed');process.exitCode=1;});
