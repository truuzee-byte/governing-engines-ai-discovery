const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Chat Threads',exact:true}).click();
    if(process.env.MODE_THREAD_ACTION==='create'){
      await page.getByRole('button',{name:'New conversation',exact:true}).click();
      await page.getByLabel('Conversation title',{exact:true}).fill('Empty direction');
      await page.getByRole('button',{name:'Create empty conversation',exact:true}).click();
      await page.getByText('Empty conversation creation queued. Wait for the stored thread reference.',{exact:true}).waitFor();
      return;
    }
    await page.getByRole('button',{name:'Read conversation',exact:true}).click();
    await page.getByLabel('Branch project ID',{exact:true}).fill('project');
    await page.getByLabel('Branch title',{exact:true}).fill('Alternate direction');
    await page.getByRole('button',{name:'Branch this stored conversation',exact:true}).click();
    await page.getByText('Branch creation queued. Wait for the new thread reference; the active conversation is unchanged.',{exact:true}).waitFor();
  }finally{await browser.close();}
})().catch(()=>{console.error('Thread branch fixture failed');process.exitCode=1;});
