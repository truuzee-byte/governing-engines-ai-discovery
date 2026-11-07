const {chromium}=require('playwright');
(async()=>{
  const target=new URL(process.env.MODE_VIEW_TEST_URL);if(target.hostname!=='127.0.0.1')throw Error('Local fixture required');
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===target.origin?r.continue():r.abort());
    const image=process.env.MODE_SOURCE_IMAGE==='1';
    await page.goto(target.href);await page.getByRole('button',{name:image?'Inspect preserved image pixels':'Measure preserved PCM audio',exact:true}).click();
    await page.getByText(image?'Source pixel inspection queued. This does not prove rendered execution, motion, or creative quality.':'Source measurement queued. This does not play audio or validate production quality.',{exact:true}).waitFor();
  }finally{await browser.close();}
})().catch(()=>{console.error('Audio source inspection fixture failed');process.exitCode=1;});
