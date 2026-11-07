const {chromium}=require('playwright');
let stage='START';
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);
  if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    stage='LOAD';await page.goto(target.href);await page.getByText('IDLE · runtime',{exact:true}).waitFor();
    stage='OPEN';
    await page.getByText('Preserve a document source',{exact:true}).click();
    const media=process.env.MODE_SOURCE_KIND||'txt';
    stage='FILE';await page.locator('#document-file').setInputFiles({name:'source.'+media,mimeType:media==='txt'?'text/plain':'application/octet-stream',
      buffer:media==='txt'?Buffer.from('Exact source café\n'.repeat(5000)):Buffer.from(process.env.MODE_SOURCE_BYTES,'base64')});
    stage='PROJECT';await page.getByLabel('Project ID',{exact:true}).fill('project');
    stage='CLASS';await page.getByLabel('Knowledge source class',{exact:true}).selectOption('EXTERNAL');
    stage='SUBMIT';await page.getByRole('button',{name:'Preserve this document draft',exact:true}).click();
    stage='RESULT';
    await page.getByText('Document draft queued. Wait for the runtime custody reference; preservation is not yet confirmed.',{exact:true}).waitFor();
  }finally{await browser.close();}
})().catch(()=>{console.error('Document intake UI fixture failed: '+stage);process.exitCode=1;});
