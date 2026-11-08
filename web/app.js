'use strict';
(async function initialize() {
const $ = id => document.getElementById(id);
// A bounded demo capability, never a provider/SSH key. Keep it only in this tab.
// Consume before the first fetch and replace this history entry to remove it.
try {
  const demo = /^#demo=([A-Za-z0-9_-]{24,80})$/.exec(window.location.hash);
  if (demo) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    $('access').value = demo[1];
  }
} catch (_) {} // If the fragment cannot be removed, leave manual access entry available.
const catalog = await fetch('/i18n.json').then(response => {
  if (!response.ok) throw new Error('Language catalog unavailable');
  return response.json();
});
let current = null, sandboxReady = false, busy = false, inferenceEnabled = false, deploymentStage = 'preparation';
let override = 'auto', noticeState = {key:'checking', error:false};
try { const saved = localStorage.getItem('sheetkeeper-language'); if (['auto','en','pt','es'].includes(saved)) override=saved; } catch (_) {}
let locale = chooseLocale(navigator.languages || [navigator.language], override);
const language = () => locale.split('-')[0];
const t = key => catalog[language()][key];
const message = raw => catalog[language()].messages[raw] || raw;
const number = value => new Intl.NumberFormat(locale).format(value);
function showNotice() { $('notice').textContent=noticeState.key?t(noticeState.key):message(noticeState.raw); $('notice').className=noticeState.error?'notice error':'notice'; }
function notice(key,error=false) { noticeState={key,error};showNotice(); }
function errorNotice(error) { noticeState={raw:error.source||error.message,error:true};showNotice(); }
function localize() {
  const previous = $('question').value;
  locale=chooseLocale(navigator.languages || [navigator.language],override);
  document.documentElement.lang=locale;$('language').value=override;$('language').setAttribute('aria-label',t('languageLabel'));
  for(const element of document.querySelectorAll('[data-i18n]')) {
    const key=element.dataset.i18n;
    const cloud=deploymentStage==='deployed';
    const copyKey=cloud&&key==='stage'?'stageCloud':cloud&&key==='footer'?'footerCloud':cloud&&key==='footerPending'?'footerCloudHint':key;
    let text=t(copyKey);
    if(key==='stage'&&!cloud)text=text.replace('{date}',new Intl.DateTimeFormat(locale,{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'}).format(new Date('2026-10-01T12:00:00Z')));
    if(key==='limits')text=text.replace('{rows}',number(2000));
    element.textContent=text;
  }
  for(const element of document.querySelectorAll('[data-i18n-placeholder]'))element.placeholder=t(element.dataset.i18nPlaceholder);
  $('chart').setAttribute('aria-label',t('chartLabel'));
  if(Object.values(catalog).some(entry=>entry.sampleQuestion===previous))$('question').value=t('sampleQuestion');
  $('mode').options[1].textContent=t(inferenceEnabled?'vultrEnabled':'vultrPending');
  if(current)render(current);else update();showNotice();
}
async function api(path, body) {
  const headers = {'Authorization': 'Bearer '+$('access').value,'X-SheetKeeper-Locale':locale};
  if(body) headers['Content-Type']='application/json';
  const response = await fetch(path,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined});
  const data=await response.json();if(!response.ok){const error=new Error(data.error||t('genericError'));error.source=data.error_source;throw error;}return data;
}
async function status(){
  try{const s=await api('/api/status');sandboxReady=s.sandbox.ready;inferenceEnabled=s.inference_enabled;
    // Deployment is a server configuration claim, separate from any executed job.
    deploymentStage=s.stage==='deployed'&&s.cloud_deployed===true?'deployed':'preparation';
    $('mode').options[1].disabled=!inferenceEnabled;$('mode').options[1].textContent=t(inferenceEnabled?'vultrEnabled':'vultrPending');
    notice(deploymentStage==='deployed'?(sandboxReady?'cloudAvailable':'cloudAwaitSandbox'):(sandboxReady?'localAvailable':'awaitDocker'));
    localize();
  }catch(e){errorNotice(e);}update();
}
function update(){const ready=current&&current.status==='ready'&&!busy;
  $('run').disabled=!ready||!sandboxReady;$('contain').disabled=!ready||!sandboxReady;$('plan').disabled=busy;
  $('sample').disabled=busy;$('file').disabled=busy;
  for(const id of ['csv','question','mode','access'])$(id).disabled=busy;
  $('runhint').textContent=t(sandboxReady?'runReady':'runBlocked');
}
function render(job){current=job;$('empty').hidden=true;$('review').hidden=false;
  $('summary').textContent=job.provider.provider==='deterministic_fixture'?t('sampleSummary'):job.summary;
  $('code').textContent=job.executed_code||job.code;$('events').replaceChildren();
  for(const event of job.events){const li=document.createElement('li');li.textContent=message(event);$('events').append(li);}
  $('result').hidden=!job.result;$('download').hidden=!job.receipt;
  if(job.result){$('rows').textContent=number(job.result.rows);$('total').textContent=number(job.result.total);$('chart').replaceChildren();
    const max=Math.max(...job.result.groups.map(g=>Math.abs(g.value)),1);
    for(const group of job.result.groups){const row=document.createElement('div');row.className='bar-row';
      const meta=document.createElement('div');meta.className='bar-meta';const name=document.createElement('span');name.textContent=group.label;
      const value=document.createElement('span');value.textContent=number(group.value);meta.append(name,value);
      const track=document.createElement('div');track.className='bar-track';const bar=document.createElement('div');bar.className='bar';bar.style.width=(Math.abs(group.value)/max*100)+'%';track.append(bar);row.append(meta,track);$('chart').append(row);}
  }update();
}
$('language').addEventListener('change',()=>{override=$('language').value;try{localStorage.setItem('sheetkeeper-language',override);}catch(_){}localize();});
window.addEventListener('languagechange',()=>{if(override==='auto')localize();});
$('access').addEventListener('change',status);
function invalidatePlan(){
  current=null;$('empty').hidden=false;$('review').hidden=true;
  $('events').replaceChildren();$('code').textContent='';$('summary').textContent='';
  $('result').hidden=true;$('download').hidden=true;notice('inputsChanged');update();
}
for(const id of ['csv','question'])$(id).addEventListener('input',invalidatePlan);
$('mode').addEventListener('change',invalidatePlan);
$('sample').addEventListener('click',async()=>{
  busy=true;update();
  try{
    const sample=await api('/api/sample');
    $('csv').value=sample.csv;$('mode').value=inferenceEnabled?'vultr':'sample';$('question').value=t('sampleQuestion');
    invalidatePlan();notice('sampleLoaded');
  }catch(e){errorNotice(e);}finally{busy=false;update();}
});
$('file').addEventListener('change',async()=>{const f=$('file').files[0];if(!f)return;if(f.size>200000){notice('csvTooLarge',true);return;}
  busy=true;update();
  try{$('csv').value=new TextDecoder('utf-8',{fatal:true}).decode(await f.arrayBuffer());invalidatePlan();notice('csvLoaded');}
  catch(e){notice('csvEncoding',true);}finally{busy=false;update();}});
$('plan').addEventListener('click',async()=>{busy=true;update();notice('planning');try{render(await api('/api/plan',{csv:$('csv').value,question:$('question').value,mode:$('mode').value}));notice('planReady');}catch(e){errorNotice(e);}finally{busy=false;update();}});
async function run(containment){busy=true;update();try{render(await api('/api/run',{job_id:current.id,containment}));notice('running');
  while(current.status==='running'){await new Promise(resolve=>setTimeout(resolve,700));render(await api('/api/jobs/'+current.id));}
  notice(['completed','contained'].includes(current.status)?current.status:'failed',current.status==='failed');
  }catch(e){errorNotice(e);}finally{busy=false;update();}}
$('run').addEventListener('click',()=>run(false));$('contain').addEventListener('click',()=>run(true));
$('download').addEventListener('click',async()=>{try{const data=await api('/api/jobs/'+current.id+'/evidence');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='sheetkeeper-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){errorNotice(e);}});
localize();await status();
})().catch(()=>{document.getElementById('notice').textContent='Não foi possível carregar a interface. / Unable to load the interface. / No se pudo cargar la interfaz.';});
