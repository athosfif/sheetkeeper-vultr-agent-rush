"""Isolated headless Chrome preview checks; never attach to a user's profile."""
import base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
import websocket
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/visual-20261001';OUT.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='sheetkeeper-chrome-',ignore_cleanup_errors=True) as tmp:
 with (OUT/'chrome-log.txt').open('w') as log:
  process=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+tmp,'about:blank'],stdout=log,stderr=log)
  ws=None
  try:
   deadline=time.monotonic()+20;p=Path(tmp)/'DevToolsActivePort'
   while not p.exists() and time.monotonic()<deadline:time.sleep(.2)
   port=p.read_text().splitlines()[0]
   tabs=json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json'))
   ws=websocket.create_connection(next(tab for tab in tabs if tab['type']=='page')['webSocketDebuggerUrl'],timeout=15,suppress_origin=True)
   sequence=0
   def cdp(method,params=None):
    global sequence
    sequence+=1;ident=sequence;ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
    while True:
     value=json.loads(ws.recv())
     if value.get('id')==ident:
      if 'error' in value:raise RuntimeError(value['error'])
      return value.get('result',{})
   def evaluate(source):
    answer=cdp('Runtime.evaluate',{'expression':source,'returnByValue':True,'awaitPromise':True})
    if 'exceptionDetails' in answer:raise AssertionError(answer['exceptionDetails'])
    return answer['result'].get('value')
   def wait(source,limit=20):
    end=time.monotonic()+limit
    while time.monotonic()<end:
     if evaluate(source):return
     time.sleep(.15)
    raise AssertionError('UI wait timed out: '+source+' STATE '+str(evaluate("JSON.stringify({lang:document.documentElement.lang,languages:navigator.languages,notice:document.getElementById('notice')?.textContent,url:location.href,title:document.title,body:document.body?.innerText.slice(0,1000)})")))
   cdp('Page.enable');cdp('Runtime.enable')
   cdp('Emulation.setLocaleOverride',{'locale':'es-MX'})
   cdp('Network.enable');cdp('Network.setExtraHTTPHeaders',{'headers':{'Accept-Language':'es-MX,es;q=0.9'}})
   cdp('Emulation.setUserAgentOverride',{'userAgent':'Mozilla/5.0 SheetKeeperLocalReview','acceptLanguage':'es-MX'})
   cdp('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
   print('NAVIGATION',cdp('Page.navigate',{'url':'http://127.0.0.1:8767/'}),flush=True)
   wait("document.getElementById('language') && document.documentElement.lang==='es-MX' && document.getElementById('notice').textContent.length>0")
   checks=[{'check':'automatic browser regional locale','value':evaluate('document.documentElement.lang'),'passed':True}]
   def screenshot(name,width):
    cdp('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<600})
    time.sleep(.25)
    metrics=cdp('Page.getLayoutMetrics')['cssContentSize']
    overflow=evaluate('document.documentElement.scrollWidth>window.innerWidth')
    assert not overflow,(name,'horizontal overflow')
    cap=cdp('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':0,'width':width,'height':metrics['height'],'scale':1}})
    (OUT/(name+'.png')).write_bytes(base64.b64decode(cap['data']))
    checks.append({'check':name,'width':width,'height':metrics['height'],'overflow':overflow,'passed':True})
   evaluate("document.getElementById('sample').click()")
   wait("document.getElementById('csv').value.includes('channel,revenue')")
   original=evaluate("document.getElementById('csv').value")
   for lang in ('es','en','pt'):
    evaluate("document.getElementById('language').value="+json.dumps(lang)+";document.getElementById('language').dispatchEvent(new Event('change'))")
    assert evaluate("document.getElementById('csv').value")==original
    screenshot(lang+'-desktop',1440);screenshot(lang+'-mobile',390)
   evaluate("document.getElementById('plan').click()")
   wait("!document.getElementById('review').hidden && !document.getElementById('run').disabled")
   evaluate("document.getElementById('run').click()")
   wait("!document.getElementById('result').hidden && !document.getElementById('plan').disabled")
   assert evaluate("document.getElementById('total').textContent")=='6.000'
   assert evaluate("document.getElementById('rows').textContent")=='6'
   screenshot('pt-result-desktop',1440);screenshot('pt-result-mobile',390)
   checks.append({'check':'real analysis via UI','rows':6,'displayed_total':'6.000','passed':True})
   cdp('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(OUT)})
   evaluate("document.getElementById('download').click()")
   end=time.monotonic()+10;download=OUT/'sheetkeeper-evidence.json'
   while not download.exists() and time.monotonic()<end:time.sleep(.2)
   receipt=json.loads(download.read_text())
   assert receipt['receipt']['destroyed'] and receipt['result']['total']==6000
   checks.append({'check':'download execution evidence','passed':True})
   evaluate("document.getElementById('plan').click()")
   wait("!document.getElementById('contain').disabled && document.getElementById('notice').textContent.includes('Plano pronto')")
   evaluate("document.getElementById('contain').click()")
   wait("document.getElementById('notice').textContent.includes('Loop interrompido') && !document.getElementById('plan').disabled")
   assert evaluate("document.getElementById('result').hidden")
   checks.append({'check':'containment via UI clears previous chart','passed':True})
   evaluate("document.getElementById('plan').click()")
   wait("!document.getElementById('run').disabled")
   evaluate("document.getElementById('run').click()")
   wait("!document.getElementById('result').hidden && !document.getElementById('plan').disabled")
   checks.append({'check':'UI recovery after containment','passed':True})
   evaluate("document.getElementById('csv').value='a,a\\n1,2';document.getElementById('plan').click()")
   wait("document.getElementById('notice').classList.contains('error')")
   checks.append({'check':'invalid CSV error displayed','passed':True})
   cdp('Page.reload')
   wait("document.documentElement.lang==='pt-BR' && document.getElementById('language').value==='pt'")
   checks.append({'check':'manual language override survives reload','passed':True})
   visited=[]
   for _ in range(25):
    cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
    cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
    visited.append(evaluate('document.activeElement.id'))
    if all(i in visited for i in ('language','sample','plan')):break
   assert all(i in visited for i in ('language','sample','plan')),visited
   checks.append({'check':'keyboard reaches language sample and plan','passed':True})
   (OUT/'checks.json').write_text(json.dumps({'browser':'isolated headless Chrome; no user profile accessed','checks':checks,'screenshots_pending_visual_inspection':True},ensure_ascii=False,indent=2)+'\n')
   print('BROWSER_CHECKS_PASSED',len(checks),flush=True)
  finally:
   if ws:ws.close()
   process.terminate()
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
