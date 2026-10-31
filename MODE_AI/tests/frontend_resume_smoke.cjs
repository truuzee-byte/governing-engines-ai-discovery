const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);
  if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();
    await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    await page.goto(target.href);
    await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Chat Threads',exact:true}).click();
    await page.locator('#panel article').filter({hasText:'Resume fixture'}).getByRole('button',{name:'Read conversation'}).click();
    await page.getByRole('button',{name:'Resume this conversation'}).click();
    await page.getByText('Thread selection queued. Waiting for the runtime to accept it.',{exact:true}).waitFor();
    console.log('THREAD_SELECTION_QUEUED');
  }finally{await browser.close();}
})().catch(()=>{console.error('Thread resume fixture failed');process.exitCode=1;});
