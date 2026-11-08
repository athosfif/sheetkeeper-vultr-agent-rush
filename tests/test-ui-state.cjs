// Regression checks for async input loading and stale plan visibility.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'web/i18n.json'), 'utf8'));
const nodes = new Map();
function element(id) {
  if (!nodes.has(id)) nodes.set(id, {
    value: id === 'question' ? catalog.en.sampleQuestion : '',
    hidden: true, disabled: false, textContent: '', files: [],
    options: [{}, {}], listeners: {},
    addEventListener(event, callback) { this.listeners[event] = callback; },
    setAttribute() {}, replaceChildren() {this.childrenCleared = true;}, append() {this.childrenCleared = false;},
  });
  return nodes.get(id);
}
const pending = {};
const deploymentNodes=['stage','footer','footerPending'].map(key=>Object.assign(element(key),{dataset:{i18n:key}}));
let serverStatus={sandbox: {ready: false}, inference_enabled: false};
let fetchCount=0;
const response = data => ({ok: true, json: async () => data});
const fixtureJob = {id: 'synthetic', status: 'ready', provider: {provider: 'deterministic_fixture'}, code: 'pass', events: [], result: null};
(async () => {
  await vm.runInNewContext(fs.readFileSync(path.join(root, 'web/app.js'), 'utf8'), {
    document: {getElementById: element, querySelectorAll: selector => selector==='[data-i18n]'?deploymentNodes:[], documentElement: {}, createElement: () => element('created')},
    navigator: {languages: ['en'], language: 'en'},
    chooseLocale: (_languages,override) => override==='auto'?'en':override, localStorage: {getItem() {return null;}, setItem() {}},
    window: {addEventListener() {}}, Intl, setTimeout,
    fetch: async url => {
      fetchCount++;
      if (url === '/i18n.json') return response(catalog);
      if (url === '/api/status') return response(serverStatus);
      if (url === '/api/plan') return response(fixtureJob);
      if (url === '/api/sample') return new Promise(resolve => {pending.sample = () => resolve(response({csv: 'channel,revenue\nSynthetic,1'}));});
      throw new Error('Unexpected route');
    },
  });
  assert.match(element('stage').textContent,/Local preparation/,'No deployment configuration keeps the local version');
  assert.equal(element('footerPending').textContent,catalog.en.footerPending);
  serverStatus={sandbox:{ready:true},inference_enabled:true,stage:'deployed',cloud_deployed:false};
  await element('access').listeners.change();
  assert.match(element('stage').textContent,/Local preparation/,'A contradictory deployment status cannot advertise cloud configuration');
  serverStatus={...serverStatus,cloud_deployed:true};
  await element('access').listeners.change();
  assert.equal(element('stage').textContent,catalog.en.stageCloud);
  assert.equal(element('footerPending').textContent,catalog.en.footerCloudHint,'Configuration copy must not claim execution proof');
  assert.equal(element('notice').textContent,catalog.en.cloudAvailable);
  assert.equal(element('mode').options[1].disabled,false);
  const beforeLanguageChange=fetchCount;
  for(const lang of ['pt','es','en']){
    element('language').value=lang;element('language').listeners.change();
    assert.equal(element('stage').textContent,catalog[lang].stageCloud,'Cloud stage survives language changes');
    assert.equal(element('footerPending').textContent,catalog[lang].footerCloudHint);
  }
  assert.equal(fetchCount,beforeLanguageChange,'Changing the label language makes no provider or status request');
  serverStatus={...serverStatus,sandbox:{ready:false}};
  await element('access').listeners.change();
  assert.equal(element('notice').textContent,catalog.en.cloudAwaitSandbox,'Cloud deployment and sandbox readiness stay distinct');
  serverStatus={sandbox:{ready:false},inference_enabled:false,stage:'preparation',cloud_deployed:false};
  await element('access').listeners.change();
  assert.match(element('stage').textContent,/Local preparation/);
  assert.equal(element('footerPending').textContent,catalog.en.footerPending,'Returning to local status restores local copy');
  const loading = element('sample').listeners.click();
  assert.equal(element('plan').disabled, true, 'Plan stays disabled while the sample is loading');
  assert.equal(element('csv').disabled, true, 'Input cannot race sample loading');
  pending.sample(); await loading;
  assert.equal(element('plan').disabled, false);
  assert.equal(element('csv').value, 'channel,revenue\nSynthetic,1');
  await element('plan').listeners.click();
  assert.equal(element('review').hidden, false);
  element('question').listeners.input();
  assert.equal(element('review').hidden, true, 'Editing the question hides the stale plan');
  assert.equal(element('empty').hidden, false);
  assert.equal(element('notice').textContent, catalog.en.inputsChanged, 'Notice must match the invalidated plan');
  assert.equal(element('events').childrenCleared, true, 'Stale execution events must be cleared');
  assert.equal(element('code').textContent, '');
  await element('plan').listeners.click();
  element('csv').listeners.input();
  assert.equal(element('review').hidden, true, 'Editing the CSV hides the stale plan');
  await element('plan').listeners.click();
  element('mode').listeners.change();
  assert.equal(element('review').hidden, true, 'Changing provider mode hides the stale plan');
  async function fragmentCase(fragment, expected) {
    nodes.clear();
    const location={hash:fragment,pathname:'/demo',search:'?lang=en'};
    const replacements=[],storageWrites=[],requests=[];
    await vm.runInNewContext(fs.readFileSync(path.join(root,'web/app.js'),'utf8'),{
      document:{getElementById:element,querySelectorAll:()=>[],documentElement:{},createElement:()=>element('created')},
      navigator:{languages:['en'],language:'en'},chooseLocale:()=> 'en',
      localStorage:{getItem(){return null;},setItem(...args){storageWrites.push(args);}},
      window:{location,history:{replaceState(_state,_title,url){replacements.push(url);location.hash='';}},addEventListener(){}},
      Intl,setTimeout,
      fetch:async (url,options)=>{
        if(expected) assert.equal(location.hash,'','Remove demo capability before even the catalog request');
        requests.push({url,options});
        if(url==='/i18n.json')return response(catalog);
        if(url==='/api/status')return response({sandbox:{ready:false},inference_enabled:false});
        throw new Error('Unexpected route');
      },
    });
    assert.equal(element('access').value,expected);
    assert.equal(storageWrites.length,0,'A demo capability is never persisted in localStorage');
    assert.deepEqual(replacements,expected?['/demo?lang=en']:[],'Preserve path/query while removing a valid capability');
    assert.equal(requests.length,2,'Opening a demo link performs only catalog/status reads');
    assert.equal(requests[1].options.headers.Authorization,'Bearer '+expected);
  }
  for(const token of ['a'.repeat(24),'synthetic_demo-access_0123456789','Z'.repeat(80)]){
    await fragmentCase('#demo='+token,token);
  }
  for(const fragment of ['','#care','#demo=short','#demo='+'a'.repeat(81),
                          '#demo='+'a'.repeat(24)+'&extra=1','#demo='+'a'.repeat(23)+'%41']){
    await fragmentCase(fragment,'');
  }
  console.log('PASS — honest stage, sandbox readiness, languages, loading/invalidation, bounded ephemeral demo links');
})().catch(error => {console.error(error); process.exitCode = 1;});
