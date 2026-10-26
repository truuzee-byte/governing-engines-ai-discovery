const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    const open=process.env.MODE_OPEN_SOURCE==='1';
    await page.goto(target.href);
    if(process.env.MODE_SEARCH_HISTORY==='1'){
      await page.getByText('Find preserved sources',{exact:true}).click();
      await page.locator('#source-namespace').selectOption(process.env.MODE_SOURCE_COLLECTION);
      await page.locator('#source-project').fill('project');await page.locator('#source-query').fill('selected');
      await page.getByLabel('Include historical versions').check();
      await page.getByRole('button',{name:'Search preserved sources',exact:true}).click();
      await page.getByText('Source search queued. Only returned exact references can be selected.',{exact:true}).waitFor();
      return;
    }
    await page.getByRole('button',{name:(open?'Open':'Use')+' source: source · version 1',exact:true}).click();
    await page.getByText(open?'Exact source retrieval queued. Prompt context selection is unchanged.':'Exact source selection queued. It is not validated reality or execution authority.',{exact:true}).waitFor();
  }finally{await browser.close();}
})().catch(()=>{console.error('Source selection fixture failed');process.exitCode=1;});
