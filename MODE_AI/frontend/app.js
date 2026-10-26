'use strict';
const states=new Set(['IDLE','LISTENING','INTERPRETING','CLARIFYING','BUILDING','VALIDATING','HALTED','COMPLETE','ERROR']);
let current=null,historyData=null,historyLoading=false,viewGeneration=0;
function showPanel(key,panel){
  const value=historyData&&['past_builds','threads'].includes(key)?historyData[key]:current&&current[key];
  if(key==='build'&&current&&operatorAccess){showBuildPanel(panel,value);return;}
  if(key==='onboarding'&&value&&panel.querySelector('form')?.dataset.profileHash===value.profile_hash)return;
  panel.replaceChildren();
  if(!value){panel.textContent='This information has not been retrieved.';return;}
  if(key==='onboarding'&&operatorAccess&&value.answers&&value.profile_hash){
    const form=document.createElement('form');form.dataset.profileHash=value.profile_hash;
    const fields={};
    for(const [name,label] of [['preferred_name','Preferred name'],['timezone','IANA timezone'],['language','Language']]){
      const wrapper=document.createElement('label'),input=document.createElement('input');wrapper.textContent=label;
      input.value=value.answers[name];input.required=true;input.maxLength=256;input.name=name;fields[name]=input;wrapper.append(input);form.append(wrapper);
    }
    const save=document.createElement('button');save.type='submit';save.textContent='Save Operator answers';
    const status=document.createElement('p');status.setAttribute('aria-live','polite');form.append(save,status);panel.append(form);
    let submission=null;
    form.addEventListener('submit',async event=>{
      event.preventDefault();save.disabled=true;
      try{
        if(!current)throw Error('Runtime unavailable');
        const request={answers:{language:fields.language.value,preferred_name:fields.preferred_name.value,timezone:fields.timezone.value},expected_profile_hash:value.profile_hash,thread_id:current.thread_id};
        const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(request)));
        const hash=Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');
        const approval={operator_id:value.operator_id,action:'OPERATOR_ONBOARDING_UPDATE',decision:'APPROVE',hash};
        const text='/onboarding '+JSON.stringify({request,approval});
        if(!submission||submission.text!==text)submission={request_id:crypto.randomUUID(),thread_id:request.thread_id,text};
        const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},body:JSON.stringify(submission)});
        if(response.status!==202)throw Error('Not queued');
        status.textContent='Answers queued. Waiting for runtime acceptance.';
      }catch(error){status.textContent='Update not confirmed. No automatic retry.';save.disabled=false;}
    });return;
  }
  if(Array.isArray(value.items)){
    const status=document.createElement('p');status.textContent=value.state;panel.append(status);
    if(key==='threads'&&operatorAccess){
      const create=document.createElement('button');create.textContent='New conversation';
      create.addEventListener('click',()=>showNewThread(panel));panel.append(create);
    }
    if(value.limited){const notice=document.createElement('p');notice.textContent='Showing '+value.items.length+' of '+value.total+' recorded builds.';panel.append(notice);}
    value.items.forEach(item=>{const card=document.createElement('article');
      card.textContent=item.title?item.title+' · '+item.thread_id+(item.active?' · active':''):
        item.request_id+' · '+item.observed_state+'\nRecorded: '+item.created_at+'\nCurrent validity: '+item.current_validity+'\nObservation: '+item.observation_id;
      if(key==='threads'&&access){const open=document.createElement('button');open.textContent='Read conversation';
        open.addEventListener('click',()=>readThread(item.thread_id,panel));card.append(open);}
      if(key==='past_builds'&&access&&item.observation_hash){const inspect=document.createElement('button');inspect.textContent='Inspect recorded evidence';
        inspect.addEventListener('click',()=>readObservation(item,panel));card.append(inspect);
        for(const earlier of (item.observations||[]).slice(1)){
          const stage=document.createElement('button');stage.textContent='Inspect stage: '+earlier.observed_state;
          stage.addEventListener('click',()=>readObservation(earlier,panel));card.append(stage);
        }
      }
      panel.append(card);});
    if(value.state==='RETRIEVED'&&!value.items.length)panel.append(document.createTextNode('No records found.'));
  }else panel.textContent=JSON.stringify(value,null,2);
}
function showNewThread(panel){
  selectedThread='new-conversation';panel.replaceChildren();
  const generation=viewGeneration,form=document.createElement('form'),label=document.createElement('label'),input=document.createElement('input');
  label.textContent='Conversation title';input.required=true;input.maxLength=256;label.append(input);
  const button=document.createElement('button');button.type='submit';button.textContent='Create empty conversation';
  const status=document.createElement('p');status.textContent='Creates an empty stored conversation. Reading or resuming it is a separate selection.';
  form.append(label,button,status);panel.append(form);let submission=null;
  form.addEventListener('submit',async event=>{
    event.preventDefault();button.disabled=true;
    try{
      if(!current||current.pending_action||generation!==viewGeneration)throw Error('Runtime scope unavailable');
      const sourceThread=current.thread_id,owner=current.operator_id,selection=JSON.stringify([sourceThread,input.value]);
      if(!submission||submission.selection!==selection){
        const request={title:input.value},approval={operator_id:owner,action:'THREAD_CREATE',decision:'APPROVE',
          hash:await sha256(new TextEncoder().encode(JSON.stringify(canonical(request))))};
        submission={selection,envelope:{request_id:crypto.randomUUID(),thread_id:sourceThread,text:'/thread create '+JSON.stringify({request,approval})}};
      }
      if(!current||current.thread_id!==sourceThread||generation!==viewGeneration)throw Error('Runtime scope changed');
      const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},body:JSON.stringify(submission.envelope)});
      if(response.status!==202)throw Error('Not queued');
      status.textContent='Empty conversation creation queued. Wait for the stored thread reference.';historyData=null;
    }catch(error){status.textContent='Creation not confirmed. No automatic retry.';button.disabled=false;}
  });
}
function showBuildPanel(panel,value){
  let form=panel.querySelector('form[data-build-thread]');
  if(!form||form.dataset.buildThread!==current.thread_id){
    panel.replaceChildren();form=document.createElement('form');form.dataset.buildThread=current.thread_id;
    const label=document.createElement('label');label.textContent='Governed build request JSON';
    const input=document.createElement('textarea');input.required=true;input.maxLength=60000;input.rows=12;label.append(input);
    const notice=document.createElement('p');notice.textContent='Supply the existing request, Understanding, and scoped authorization envelope. Submission does not grant execution authority.';
    const submit=document.createElement('button');submit.type='submit';submit.textContent='Submit governed build request';
    const status=document.createElement('p');status.setAttribute('aria-live','polite');status.dataset.buildStatus='';
    form.append(label,notice,submit,status);panel.append(form);
    let submission=null;
    input.addEventListener('input',()=>{
      status.textContent='';
      submit.disabled=!current||!!current.pending_action||['HALTED','ERROR','BUILDING','VALIDATING'].includes(current.state);
    });
    form.addEventListener('submit',async event=>{
      event.preventDefault();submit.disabled=true;
      try{
        if(!current||current.thread_id!==form.dataset.buildThread||current.pending_action||['HALTED','ERROR','BUILDING','VALIDATING'].includes(current.state))throw Error('Runtime not available');
        const parsed=JSON.parse(input.value);
        if(!parsed||Array.isArray(parsed)||Object.keys(parsed).sort().join(',')!=='authorization,request,understanding')throw Error('Complete envelope required');
        // Preserve the exact input. The canonical runtime parser rejects duplicate fields.
        const text='/build '+input.value;
        if(!submission||submission.text!==text)submission={request_id:crypto.randomUUID(),thread_id:current.thread_id,text};
        const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},body:JSON.stringify(submission)});
        if(response.status!==202)throw Error('Not queued');
        status.textContent='Build request queued for canonical runtime validation. No execution or success inferred.';
      }catch(error){status.textContent='Build request not confirmed. Review the envelope and runtime state; no automatic retry.';submit.disabled=false;}
    });
  }
  const disabled=!!current.pending_action||['HALTED','ERROR','BUILDING','VALIDATING'].includes(current.state);
  if(disabled)form.querySelector('button').disabled=true;
  else if(!form.querySelector('[data-build-status]').textContent.startsWith('Build request queued'))form.querySelector('button').disabled=false;
  let outcome=panel.querySelector('[data-build-outcome]');
  if(!outcome){outcome=document.createElement('pre');outcome.dataset.buildOutcome='';panel.append(outcome);}
  outcome.textContent=value?JSON.stringify(value,null,2):'No build result has been recorded in this active runtime.';
}
let selectedThread=null;
async function readObservation(item,panel){
  const generation=viewGeneration;
  selectedThread='observation:'+item.observation_id;
  try{
    const response=await fetch('/observation?id='+encodeURIComponent(item.observation_id)+'&hash='+encodeURIComponent(item.observation_hash),{headers:{Authorization:'Bearer '+access},cache:'no-store'});
    if(!response.ok)throw Error('Observation unavailable');
    const value=await response.json();
    if(generation!==viewGeneration||selectedThread!=='observation:'+item.observation_id)return;
    if(value.contract!=='ModeObservationView/1'||value.observation_hash!==item.observation_hash||value.execution_authority!==false||value.current_validity!=='NOT_REVALIDATED')throw Error('Invalid observation view');
    panel.replaceChildren();const label=document.createElement('p');label.textContent='Recorded evidence · current validity not revalidated';
    const details=document.createElement('pre');details.textContent=JSON.stringify(value.observation,null,2);panel.append(label,details);
  }catch(error){if(generation===viewGeneration&&selectedThread==='observation:'+item.observation_id)panel.textContent='Recorded evidence unavailable or changed. No substitute displayed.';}
}
async function readThread(id,panel){
  const generation=viewGeneration;
  selectedThread=id;
  try{
    const response=await fetch('/thread?id='+encodeURIComponent(id),{headers:{Authorization:'Bearer '+access},cache:'no-store'});
    if(!response.ok)throw Error('Thread unavailable');
    const value=await response.json();
    if(generation!==viewGeneration||selectedThread!==id)return;
    if(value.contract!=='ModeThreadView/1'||value.thread_id!==id||value.execution_authority!==false||!Array.isArray(value.messages))throw Error('Invalid thread');
    panel.replaceChildren();const title=document.createElement('p');title.textContent=value.title+' · stored conversation · active thread unchanged';panel.append(title);
    value.messages.forEach(m=>{if(typeof m.content!=='string'||typeof m.role!=='string')throw Error('Invalid message');
      const entry=document.createElement('article');entry.textContent=m.role+': '+m.content;panel.append(entry);});
    if(operatorAccess&&current){
      const branch=document.createElement('form'),branchProject=document.createElement('input'),branchTitle=document.createElement('input');
      const projectLabel=document.createElement('label'),titleLabel=document.createElement('label');
      projectLabel.textContent='Branch project ID';branchProject.required=true;branchProject.maxLength=256;branchProject.value=value.continuity?.project_id||'';projectLabel.append(branchProject);
      titleLabel.textContent='Branch title';branchTitle.required=true;branchTitle.maxLength=256;titleLabel.append(branchTitle);
      const fork=document.createElement('button');fork.type='submit';fork.textContent='Branch this stored conversation';
      const forkStatus=document.createElement('p');forkStatus.textContent='Copies the exact stored conversation into a separate thread. Switching to it is a separate action; no session answers or execution authority are inherited.';
      branch.append(projectLabel,titleLabel,fork,forkStatus);panel.append(branch);let forkSubmission=null;
      branch.addEventListener('submit',async event=>{
        event.preventDefault();fork.disabled=true;
        try{
          if(!current||generation!==viewGeneration||current.pending_action)throw Error('Scope unavailable');
          const sourceThread=current.thread_id,selection=JSON.stringify([sourceThread,branchProject.value,branchTitle.value]);
          if(!forkSubmission||forkSubmission.selection!==selection){
            const request={source_thread_id:id,expected_source_hash:value.thread_hash,project_id:branchProject.value,title:branchTitle.value};
            const approval={operator_id:value.operator_id,action:'THREAD_FORK',decision:'APPROVE',hash:await sha256(new TextEncoder().encode(JSON.stringify(canonical(request))))};
            forkSubmission={selection,envelope:{request_id:crypto.randomUUID(),thread_id:sourceThread,text:'/thread fork '+JSON.stringify({request,approval})}};
          }
          if(!current||current.thread_id!==sourceThread||generation!==viewGeneration)throw Error('Scope changed');
          const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},body:JSON.stringify(forkSubmission.envelope)});
          if(response.status!==202)throw Error('Not queued');
          forkStatus.textContent='Branch creation queued. Wait for the new thread reference; the active conversation is unchanged.';historyData=null;
        }catch(error){forkStatus.textContent='Branch creation not confirmed. No automatic retry.';fork.disabled=false;}
      });
      const preservation=document.createElement('form'),label=document.createElement('label'),project=document.createElement('input');
      label.textContent='Vault project ID';project.required=true;project.maxLength=256;project.value=value.continuity?.project_id||'';label.append(project);
      const preserve=document.createElement('button');preserve.type='submit';preserve.textContent='Preserve this stored version in Vault';
      const status=document.createElement('p');status.textContent='Explicit preservation copies this stored thread version, including its message metadata. It does not validate its contents.';
      preservation.append(label,preserve,status);panel.append(preservation);let submission=null;
      preservation.addEventListener('submit',async event=>{
        event.preventDefault();preserve.disabled=true;
        try{
          if(!current||generation!==viewGeneration||current.pending_action||!project.value.trim())throw Error('Scope unavailable');
          const sourceThread=current.thread_id,selection=JSON.stringify([sourceThread,project.value]);
          if(!submission||submission.selection!==selection){
            const request={object_id:'thread-preservation-'+crypto.randomUUID(),thread_id:id,expected_thread_hash:value.thread_hash,
              project_id:project.value,expected_previous:null};
            const approval={operator_id:value.operator_id,action:'VAULT_PRESERVE_THREAD',decision:'APPROVE',
              hash:await sha256(new TextEncoder().encode(JSON.stringify(canonical(request))))};
            submission={selection,envelope:{request_id:crypto.randomUUID(),thread_id:sourceThread,
              text:'/vault preserve_thread '+JSON.stringify({request,approval})}};
          }
          if(!current||current.thread_id!==sourceThread||generation!==viewGeneration)throw Error('Scope changed');
          const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},body:JSON.stringify(submission.envelope)});
          if(response.status!==202)throw Error('Not queued');
          status.textContent='Exact stored-thread preservation queued. Wait for the Vault custody reference.';
        }catch(error){status.textContent='Vault preservation not confirmed. No automatic retry.';preserve.disabled=false;}
      });
    }
    if(operatorAccess&&current&&current.thread_id!==id){
      const resume=document.createElement('button');resume.textContent='Resume this conversation';
      resume.addEventListener('click',async()=>{
        resume.disabled=true;
        try{
          if(!current||generation!==viewGeneration)throw Error('View changed');
          const request={expected_hash:value.thread_hash,from_thread_id:current.thread_id,thread_id:id};
          const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(request)));
          const hash=Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');
          const approval={operator_id:value.operator_id,action:'THREAD_ACTIVATE',decision:'APPROVE',hash};
          const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},
            body:JSON.stringify({request_id:crypto.randomUUID(),thread_id:request.from_thread_id,
              text:'/thread activate '+JSON.stringify({request,approval})})});
          if(response.status!==202)throw Error('Not queued');
          title.textContent='Thread selection queued. Waiting for the runtime to accept it.';
          historyData=null;
        }catch(error){title.textContent='Thread selection not confirmed. No automatic retry.';}
      });panel.append(resume);
    }
  }catch(error){if(generation===viewGeneration&&selectedThread===id){panel.textContent='Stored conversation unavailable. No substitute displayed.';}}
}
function render(value,live=false){
  if(value.contract!=='ModePresentation/1'||value.source!=='ACTIVE_RUNTIME_SNAPSHOT'||!states.has(value.state)||!Array.isArray(value.messages)||value.execution_authority!==false)throw Error('Invalid runtime snapshot');
  if(value.messages.some(m=>typeof m.content!=='string'||typeof m.role!=='string'))throw Error('Invalid conversation');
  if(current&&current.thread_id!==value.thread_id){historyData=null;selectedThread=null;pendingSubmission=null;viewGeneration++;}
  current=value;document.getElementById('state').textContent=value.state+(live?' · runtime':' · captured');
  document.getElementById('thread').textContent=value.title+' · '+value.thread_id;
  if(['WRITE_CONFLICT','LOCAL_CHANGES_NOT_PERSISTED'].includes(value.thread_retention?.state))
    document.getElementById('thread').append(document.createTextNode(' · '+value.thread_retention.state+' — current conversation changes are not confirmed persisted'));
  const area=document.getElementById('messages');area.replaceChildren();
  value.messages.forEach(m=>{const item=document.createElement('article'),role=document.createElement('strong'),content=document.createElement('span');role.textContent=m.role;content.textContent=m.content;item.append(role,content);area.append(item);});
  const operation=document.getElementById('operation-result');operation.replaceChildren();operation.hidden=!value.operation;
  if(value.operation){
    if(value.operation.contract!=='ModeOperationView/1'||value.operation.execution_authority!==false)throw Error('Invalid operation view');
    const label=document.createElement('p');label.textContent=value.operation.command+' · '+value.operation.state;operation.append(label);
    const detail=document.createElement('pre');detail.textContent=value.operation.content_omitted?
      'Result exceeds the display limit. Source content was not substituted or truncated.':JSON.stringify(value.operation.result??{error_type:value.operation.error_type},null,2);
    operation.append(detail);
    if(value.operation.result_reference){const reference=document.createElement('pre');reference.textContent=JSON.stringify(value.operation.result_reference,null,2);operation.append(reference);}
    if(live&&access&&value.operation.export_reference){
      const reference=value.operation.export_reference,button=document.createElement('button'),status=document.createElement('p');
      button.textContent='Download retained document export';operation.append(button,status);
      button.addEventListener('click',async()=>{
        button.disabled=true;
        try{
          const response=await fetch('/operation-export?'+new URLSearchParams({hash:reference.view_hash}),{headers:{Authorization:'Bearer '+access},cache:'no-store'});
          if(!response.ok)throw Error('Retained export unavailable');
          const bytes=new Uint8Array(await response.arrayBuffer()),checksum=await sha256(bytes);
          if(checksum!==reference.sha256||checksum!==response.headers.get('X-Content-SHA256')||bytes.length!==reference.byte_length)throw Error('Export changed');
          const extensions={TEXT:'txt',JSON:'json',HTML:'html',MODEL_JSON:'model.json'};if(!extensions[reference.format])throw Error('Unknown export');
          const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'})),link=document.createElement('a');
          link.href=url;link.download='mode-export-'+checksum.slice(0,12)+'.'+extensions[reference.format];link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
          status.textContent='Retained export bytes handed to browser download. Rendering remains unproven.';
        }catch(error){status.textContent='Retained export unavailable or changed. No substitute generated.';}
      });
    }
    const stored=value.operation.result_reference||value.operation.result;
    if(live&&operatorAccess&&stored?.namespace==='DOCUMENT'){
      let sourceSchema=stored.declared_source_schema;
      if(!sourceSchema&&typeof stored.content==='string'){try{sourceSchema=JSON.parse(stored.content)?.schema_version;}catch(error){}}
      const exportForm=document.createElement('form'),format=document.createElement('select'),exportButton=document.createElement('button'),exportStatus=document.createElement('p');
      format.setAttribute('aria-label','Document export format');
      for(const name of (['AudioSource/1','ImageSource/1'].includes(sourceSchema)?['JSON','MODEL_JSON']:['TEXT','HTML','JSON','MODEL_JSON'])){
        const option=document.createElement('option');option.value=name;option.textContent=name;format.append(option);
      }
      exportButton.type='submit';exportButton.textContent='Prepare document export';exportForm.append(format,exportButton,exportStatus);operation.append(exportForm);
      exportForm.addEventListener('submit',async event=>{
        event.preventDefault();exportButton.disabled=true;
        try{
          if(!current||current.thread_id!==value.thread_id||current.pending_action)throw Error('Scope changed');
          const request={object_id:stored.object_id,version:stored.version,expected_hash:stored.record_hash,format:format.value};
          const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},
            body:JSON.stringify({request_id:crypto.randomUUID(),thread_id:value.thread_id,text:'/documents export '+JSON.stringify(request)})});
          if(response.status!==202)throw Error('Not queued');
          exportStatus.textContent='Exact document export queued. Download becomes available when serialization completes.';
        }catch(error){exportStatus.textContent='Export request not confirmed. No automatic retry.';}
      });
      if(['AudioSource/1','ImageSource/1'].includes(sourceSchema)){
        const audio=sourceSchema==='AudioSource/1';
        const inspect=document.createElement('button'),status=document.createElement('p');inspect.textContent=audio?'Measure preserved PCM audio':'Inspect preserved image pixels';operation.append(inspect,status);
        inspect.addEventListener('click',async()=>{
          inspect.disabled=true;
          try{
            if(!current||current.thread_id!==value.thread_id||current.pending_action)throw Error('Scope changed');
            const reference={object_id:stored.object_id,version:stored.version,expected_hash:stored.record_hash};
            const request={...(audio?{reference}:{references:[reference]}),project_id:stored.project_id||stored.metadata?.project_id};
            const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},
              body:JSON.stringify({request_id:crypto.randomUUID(),thread_id:value.thread_id,text:'/creative '+(audio?'inspect_audio ':'inspect_frames ')+JSON.stringify(request)})});
            if(response.status!==202)throw Error('Not queued');
            status.textContent=audio?'Source measurement queued. This does not play audio or validate production quality.':'Source pixel inspection queued. This does not prove rendered execution, motion, or creative quality.';
          }catch(error){status.textContent='Source inspection not confirmed. No automatic retry.';}
        });
      }
    }
    if(live&&access&&stored?.namespace==='DOCUMENT'&&stored.record_hash){
      const getSource=document.createElement('button');getSource.textContent='Download preserved source bytes';
      const downloadStatus=document.createElement('p');downloadStatus.setAttribute('aria-live','polite');operation.append(getSource,downloadStatus);
      getSource.addEventListener('click',async()=>{
        getSource.disabled=true;
        try{
          const query=new URLSearchParams({object_id:stored.object_id,version:String(stored.version),hash:stored.record_hash});
          const response=await fetch('/document-source?'+query,{headers:{Authorization:'Bearer '+access},cache:'no-store'});
          if(!response.ok||response.headers.get('X-Source-Record-Hash')!==stored.record_hash)throw Error('Source unavailable');
          const bytes=new Uint8Array(await response.arrayBuffer()),hash=await sha256(bytes);
          if(hash!==response.headers.get('X-Content-SHA256'))throw Error('Source changed');
          const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'})),link=document.createElement('a');
          link.href=url;link.download='mode-source-'+hash.slice(0,12)+'.bin';link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
          downloadStatus.textContent='Exact preserved source handed to browser download. No regenerated substitute.';
        }catch(error){downloadStatus.textContent='Preserved source unavailable or changed. No substitute downloaded.';}
      });
    }
    const search=value.operation.result;
    if(live&&operatorAccess&&search&&['KnowledgeSearch/1','CustodySearch/1'].includes(search.contract)&&Array.isArray(search.matches)){
      const notice=document.createElement('p');notice.textContent='Search does not select authority. Choosing one source replaces the pending selection in this collection for the next response only.';operation.append(notice);
      for(const match of search.matches){
        if(search.contract!=='KnowledgeSearch/1'&&search.namespace!=='VAULT')continue;
        const open=document.createElement('button');open.textContent='Open source: '+match.reference.object_id+' · version '+match.reference.version;
        open.addEventListener('click',async()=>{
          open.disabled=true;
          try{
            if(!current||current.thread_id!==value.thread_id||current.pending_action)throw Error('Scope changed');
            const reference={object_id:match.reference.object_id,version:match.reference.version,expected_hash:match.reference.expected_hash};
            const text=(search.contract==='KnowledgeSearch/1'?'/documents get ':'/vault get ')+JSON.stringify(reference);
            const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},
              body:JSON.stringify({request_id:crypto.randomUUID(),thread_id:value.thread_id,text})});
            if(response.status!==202)throw Error('Not queued');
            notice.textContent='Exact source retrieval queued. Prompt context selection is unchanged.';
          }catch(error){notice.textContent='Source retrieval not confirmed. No automatic retry.';}
        });operation.append(open);
        const choose=document.createElement('button');choose.textContent='Use source: '+match.reference.object_id+' · version '+match.reference.version;
        choose.addEventListener('click',async()=>{
          choose.disabled=true;
          try{
            if(!current||current.thread_id!==value.thread_id||current.pending_action)throw Error('Scope changed');
            const text=search.contract==='KnowledgeSearch/1'?'/knowledge context '+JSON.stringify([match.reference]):
              '/vault context '+JSON.stringify({references:[match.reference],project_id:search.project_id});
            const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},
              body:JSON.stringify({request_id:crypto.randomUUID(),thread_id:value.thread_id,text})});
            if(response.status!==202)throw Error('Not queued');
            notice.textContent='Exact source selection queued. It is not validated reality or execution authority.';
          }catch(error){notice.textContent='Source selection not confirmed. No automatic retry.';}
        });operation.append(choose);
      }
    }
    const exported=value.operation.result;
    if(live&&!value.operation.content_omitted&&exported?.contract==='DocumentExport/1'){
      const download=document.createElement('button');download.textContent='Download exact document export';
      const status=document.createElement('p');status.setAttribute('aria-live','polite');operation.append(download,status);
      download.addEventListener('click',async()=>{
        download.disabled=true;
        try{
          if(exported.state!=='SERIALIZED'||exported.rendered_output_observed!==false||typeof exported.content!=='string')throw Error('Invalid export');
          const bytes=new TextEncoder().encode(exported.content);
          const hashed=await crypto.subtle.digest('SHA-256',bytes);
          const hash=Array.from(new Uint8Array(hashed),x=>x.toString(16).padStart(2,'0')).join('');
          const extensions={TEXT:'txt',JSON:'json',HTML:'html',MODEL_JSON:'model.json'};
          if(hash!==exported.sha256||bytes.length!==exported.byte_length||!extensions[exported.format])throw Error('Export changed');
          const blob=new Blob([bytes],{type:'application/octet-stream'}),url=URL.createObjectURL(blob);
          const link=document.createElement('a');link.href=url;link.download='mode-document-'+hash.slice(0,12)+'.'+extensions[exported.format];
          link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
          status.textContent='Verified export handed to browser download. Rendering and visual correctness remain unproven.';
        }catch(error){status.textContent='Export download blocked: content or contract verification failed.';}
      });
    }
  }
  const consent=document.getElementById('pending-consent'),pending=value.pending_action;
  consent.hidden=!pending;
  if(!pending){consent.replaceChildren();delete consent.dataset.action;}
  else if(consent.dataset.action!==pending.action_id){
    consent.dataset.action=pending.action_id;consent.replaceChildren();
    const prompt=document.createElement('p');prompt.textContent=pending.action_type==='SAVE_MEMORY'?'Save this exact memory?':'Operator clarification required.';consent.append(prompt);
    if(pending.action_type==='SAVE_MEMORY'){
      const content=document.createElement('pre');content.textContent=pending.memory_text;consent.append(content);
      if(operatorAccess)for(const [label,answer] of [['Save persistently','yes'],['Do not save','no'],['Session only','session-only']]){
        const button=document.createElement('button');button.textContent=label;
        button.addEventListener('click',async()=>{
          consent.querySelectorAll('button').forEach(b=>b.disabled=true);
          try{
            const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},
              body:JSON.stringify({request_id:crypto.randomUUID(),thread_id:value.thread_id,pending_action_id:pending.action_id,text:answer})});
            if(response.status!==202)throw Error('Not queued');prompt.textContent='Choice queued for this memory proposal.';
          }catch(error){prompt.textContent='Choice not confirmed. No automatic retry.';}
        });consent.append(button);
      }
    }
  }
  document.getElementById('connection').textContent=live?(operatorAccess?'Connected to the Operator input queue. Inputs use normal runtime governance.':'Connected to the local read-only runtime view. Use the Operator command surface for actions.'):'Loaded snapshot (not independently authenticated). Live command submission is not connected.';
  document.getElementById('document-intake').hidden=!(live&&operatorAccess);
  document.getElementById('source-discovery').hidden=!(live&&operatorAccess);
}
document.getElementById('snapshot').addEventListener('change',async e=>{
  try{const file=e.target.files[0];if(!file||file.size>2000000)throw Error('Snapshot missing or too large');render(JSON.parse(await file.text()));}
  catch(error){document.getElementById('state').textContent='Snapshot unavailable';document.getElementById('connection').textContent='Snapshot rejected. No runtime state inferred.';document.getElementById('messages').replaceChildren();document.getElementById('thread').textContent='';document.getElementById('panel').textContent='';current=null;}
});
document.querySelectorAll('nav button').forEach(button=>button.addEventListener('click',()=>{
  selectedThread=null;
  document.querySelectorAll('nav button').forEach(b=>b.removeAttribute('aria-current'));button.setAttribute('aria-current','page');
  document.getElementById('heading').textContent=button.textContent;const chat=button.textContent==='Chat Mode';
  document.getElementById('messages').hidden=!chat;const panel=document.getElementById('panel');panel.hidden=chat;
  const key={'Build Mode':'build','Past Builds':'past_builds','Chat Threads':'threads','Operator Onboarding':'onboarding'}[button.textContent];
  showPanel(key,panel);
  if(access && ['past_builds','threads'].includes(key) && !historyData && !historyLoading){
    historyLoading=true;
    const requestedGeneration=viewGeneration;
    fetch('/history',{headers:{Authorization:'Bearer '+access},cache:'no-store'}).then(r=>{
      if(!r.ok)throw Error('History unavailable');return r.json();
    }).then(value=>{
      if(requestedGeneration!==viewGeneration)return;
      if(value.contract!=='ModeHistory/1'||value.execution_authority!==false)throw Error('Invalid history');
      historyData=value;
      const selected=document.querySelector('nav button[aria-current]');if(selected)selected.click();
    }).catch(()=>{if(requestedGeneration!==viewGeneration)return;historyData={past_builds:{state:'UNAVAILABLE',items:[]},threads:{state:'UNAVAILABLE',items:[]}};
      const selected=document.querySelector('nav button[aria-current]');if(selected)selected.click();
    }).finally(()=>{historyLoading=false;});
  }
}));
const access=new URLSearchParams(window.location.hash.slice(1)).get('access');
const operatorAccess=new URLSearchParams(window.location.hash.slice(1)).get('operator_access');
const operatorForm=document.getElementById('operator-form');
let sourceSubmission=null;
document.getElementById('source-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.currentTarget.querySelector('button'),status=document.getElementById('source-status');button.disabled=true;
  try{
    if(!current||!operatorAccess||current.pending_action)throw Error('Runtime unavailable');
    const namespace=document.getElementById('source-namespace').value;
    if(!['knowledge','vault'].includes(namespace))throw Error('Unknown collection');
    const request={query:document.getElementById('source-query').value,project_id:document.getElementById('source-project').value,
      include_history:document.getElementById('source-history').checked};
    const text='/'+namespace+' search '+JSON.stringify(request);
    if(!sourceSubmission||sourceSubmission.text!==text||sourceSubmission.thread_id!==current.thread_id)
      sourceSubmission={request_id:crypto.randomUUID(),thread_id:current.thread_id,text};
    const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},body:JSON.stringify(sourceSubmission)});
    if(response.status!==202)throw Error('Not queued');
    status.textContent='Source search queued. Only returned exact references can be selected.';
  }catch(error){status.textContent='Search not confirmed. No automatic retry.';}
  finally{button.disabled=false;}
});
function canonical(value){
  if(Array.isArray(value))return value.map(canonical);
  if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));
  return value;
}
async function sha256(bytes){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');}
let documentSubmission=null;
document.getElementById('document-form').addEventListener('submit',async event=>{
  event.preventDefault();const form=event.currentTarget,button=form.querySelector('button'),status=document.getElementById('document-status');button.disabled=true;
  try{
    if(!current||!operatorAccess||!current.operator_id||current.pending_action||['HALTED','ERROR','BUILDING','VALIDATING'].includes(current.state))throw Error('Runtime unavailable');
    const owner=current.operator_id,thread=current.thread_id,file=document.getElementById('document-file').files[0];
    if(!file||!file.size||file.size>8*1024*1024)throw Error('Source size exceeds bound');
    const ext=file.name.split('.').pop().toLowerCase(),format=ext==='pdf'?'PDF':ext==='docx'?'DOCX':['txt','json','md'].includes(ext)?'UTF8_TEXT':ext==='wav'?'WAV':['png','jpg','jpeg','webp'].includes(ext)?'IMAGE':null;
    if(!format)throw Error('Unsupported source type');
    const bytes=new Uint8Array(await file.arrayBuffer()),hash=await sha256(bytes);
    if(format==='UTF8_TEXT')new TextDecoder('utf-8',{fatal:true}).decode(bytes);
    const chunks=[];for(let i=0;i<bytes.length;i+=8192)chunks.push(String.fromCharCode(...bytes.subarray(i,i+8192)));
    const project=document.getElementById('document-project').value,knowledgeClass=document.getElementById('document-class').value;
    if(!project.trim()||!['SYSTEM','INTERNAL','EXTERNAL'].includes(knowledgeClass))throw Error('Source scope required');
    const identity=JSON.stringify([owner,thread,hash,file.name,project,knowledgeClass]);
    if(!documentSubmission||documentSubmission.identity!==identity){
      const source={data:btoa(chunks.join('')),sha256:hash};
      const content=JSON.stringify(format==='WAV'?{schema_version:'AudioSource/1',encoding:'BASE64_WAV',...source}:
        format==='IMAGE'?{schema_version:'ImageSource/1',encoding:'BASE64',...source}:
        {schema_version:'DocumentBinary/1',format,encoding:'BASE64',...source});
      const request={object_id:'document-'+crypto.randomUUID(),content,kind:'DRAFT',visual_authority:format==='IMAGE'?'REFERENCE':'NOT_APPLICABLE',
        source_reference:'operator-file:'+file.name+':sha256:'+hash,authority:'operator-supplied source',project_id:project,
        thread_id:thread,expected_previous:null,validation_references:[],knowledge_class:knowledgeClass};
      const approval={operator_id:owner,action:'DOCUMENT_INTAKE',decision:'APPROVE',hash:await sha256(new TextEncoder().encode(JSON.stringify(canonical(request))))};
      documentSubmission={identity,envelope:{request_id:crypto.randomUUID(),thread_id:thread,text:'/documents intake '+JSON.stringify({request,approval})}};
    }
    if(!current||current.operator_id!==owner||current.thread_id!==thread||current.pending_action)throw Error('Scope changed');
    const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},body:JSON.stringify(documentSubmission.envelope)});
    if(response.status!==202)throw Error('Not queued');
    status.textContent='Document draft queued. Wait for the runtime custody reference; preservation is not yet confirmed.';
  }catch(error){status.textContent='Document not confirmed. Check file, scope, and runtime state; no automatic retry.';}
  finally{button.disabled=false;}
});
let pendingSubmission=null;
if(operatorAccess&&access&&window.location.protocol==='http:'&&window.location.hostname==='127.0.0.1')operatorForm.hidden=false;
operatorForm.addEventListener('submit',async event=>{
  event.preventDefault();if(!current||!operatorAccess)return;
  const text=document.getElementById('operator-text').value;if(!text.trim())return;
  const button=operatorForm.querySelector('button');button.disabled=true;
  if(!pendingSubmission||pendingSubmission.thread_id!==current.thread_id||pendingSubmission.text!==text)
    pendingSubmission={request_id:crypto.randomUUID(),thread_id:current.thread_id,text};
  if(current.pending_action)pendingSubmission.pending_action_id=current.pending_action.action_id;
  else delete pendingSubmission.pending_action_id;
  try{
    const response=await fetch('/input',{method:'POST',headers:{Authorization:'Bearer '+operatorAccess,'Content-Type':'application/json'},
      body:JSON.stringify(pendingSubmission)});
    if(response.status!==202)throw Error('Input not queued');
    pendingSubmission=null;
    document.getElementById('operator-text').value='';document.getElementById('input-status').textContent='Queued for the normal runtime. No execution approval inferred.';
  }catch(error){document.getElementById('input-status').textContent='Submission not confirmed. No automatic retry.';}
  finally{button.disabled=false;}
});
if(access && window.location.protocol==='http:' && window.location.hostname==='127.0.0.1'){
  window.history.replaceState(null,'',window.location.pathname);
  document.getElementById('snapshot').disabled=true;
  async function refresh(){
    try{
      const response=await fetch('/state',{headers:{Authorization:'Bearer '+access},cache:'no-store'});
      if(!response.ok)throw Error('Runtime unavailable');
      render(await response.json(),true);
      const selected=document.querySelector('nav button[aria-current]');
      if(selected && selected.textContent!=='Chat Mode'&&!selectedThread)selected.click();
      window.setTimeout(refresh,1000);
    }catch(error){
      current=null;historyData=null;selectedThread=null;viewGeneration++;document.getElementById('state').textContent='Runtime unavailable';
      operatorForm.hidden=true;
      document.getElementById('document-intake').hidden=true;
      document.getElementById('source-discovery').hidden=true;
      document.getElementById('connection').textContent='Live view stopped. No current state inferred.';
      document.getElementById('messages').replaceChildren();document.getElementById('panel').textContent='';
      document.getElementById('operation-result').replaceChildren();document.getElementById('operation-result').hidden=true;
      document.getElementById('pending-consent').replaceChildren();document.getElementById('pending-consent').hidden=true;
      document.getElementById('thread').textContent='';
    }
  }
  refresh();
}
