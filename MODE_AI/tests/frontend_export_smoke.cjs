const {chromium}=require('playwright');
const crypto=require('crypto');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);
  if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();let requests=0;
    await page.route('**/*',r=>{
      if(r.request().method()==='POST')requests++;
      return new URL(r.request().url()).origin===target.origin?r.continue():r.abort();
    });
    await page.goto(target.href);
    const large=process.env.MODE_EXPORT_LARGE==='1';
    const button=page.getByRole('button',{name:large?'Download retained document export':'Download exact document export',exact:true});
    if(process.env.MODE_EXPORT_BAD==='1'){
      let downloads=0;page.on('download',()=>downloads++);
      await button.click();await page.getByText(large?'Retained export unavailable or changed. No substitute generated.':'Export download blocked: content or contract verification failed.',{exact:true}).waitFor();
      if(downloads)throw Error('Changed export downloaded');
    }else{
      const promise=page.waitForEvent('download');await button.click();const download=await promise;
      const stream=await download.createReadStream(),chunks=[];for await(const chunk of stream)chunks.push(chunk);
      if(crypto.createHash('sha256').update(Buffer.concat(chunks)).digest('hex')!==process.env.MODE_EXPORT_HASH)throw Error('Download mismatch');
    }
    if(requests)throw Error('Export must not submit runtime commands');
  }finally{await browser.close();}
})().catch(()=>{console.error('Bounded document download fixture failed');process.exitCode=1;});
