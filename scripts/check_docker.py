"""Real local Docker rehearsal; synthetic input, no model calls or cloud resources."""
import csv,json,os,subprocess,time
from collections import defaultdict
from pathlib import Path
from sheetkeeper.sandbox import DockerSandbox
from sheetkeeper.planner import SAMPLE_CODE,SAMPLE_QUESTION
from sheetkeeper.contracts import validate_result
from sheetkeeper.jobs import Jobs
ROOT=Path(__file__).resolve().parents[1]
CSV=(ROOT/'fixtures/sales.csv').read_text()
OUT=ROOT/'evidence/docker-rehearsal-20261001.json'
sandbox=DockerSandbox()
ready=sandbox.preflight()
assert ready['ready'],ready
records=[]

def check(name,code,expect,timeout=3):
    output=sandbox.execute(code,CSV,timeout)
    gone=subprocess.run([sandbox.binary,'container','inspect',output['container']],capture_output=True,timeout=5).returncode!=0
    output['removal_independently_checked']=gone
    records.append({'case':name,'output':output})
    OUT.write_text(json.dumps({'environment':'local Docker Desktop Linux VM; not Vultr; not rootless deployment proof','preflight':ready,'checks':records,'complete':False},ensure_ascii=False,indent=2)+'\n')
    assert output['destroyed'] and gone,(name,'container left behind')
    expect(output)
    print(name,'passed',output['elapsed_ms'],'ms',flush=True)
    return output

def normal(x):
    actual=validate_result(x['result']);expected=defaultdict(float)
    for row in csv.DictReader(CSV.splitlines()):expected[row['channel']]+=float(row['revenue'])
    assert actual['rows']==6 and actual['total']==sum(expected.values())
    assert {g['label']:g['value'] for g in actual['groups']}==dict(expected)
    assert x['exit_code']==0 and not x['timed_out']

def contains(x):assert x['timed_out'] and x['result'] is None

def rejected(x):assert x['exit_code']!=0 and x['result'] is None

check('normal-real-analysis',SAMPLE_CODE,normal,15)
check('infinite-loop-timeout','while True:\n    pass\n',contains,3)
check('recovery-after-timeout',SAMPLE_CODE,normal,15)
probe='''import json, os, socket
from pathlib import Path
assert os.getuid()==10001
assert not Path('/var/run/docker.sock').exists()
assert not Path('/Users/athvs').exists()
assert not Path('/Volumes/FIGUEIRA').exists()
assert not any(k in os.environ for k in ('VULTR_INFERENCE_API_KEY','SHEETKEEPER_ACCESS_CODE','AWS_SECRET_ACCESS_KEY'))
try:
    Path('/root-write-probe').write_text('x')
except OSError: pass
else: raise AssertionError('root filesystem writable')
try:
    socket.create_connection(('1.1.1.1',443),timeout=1)
except OSError: pass
else: raise AssertionError('network available')
Path('/work/result.json').write_text(json.dumps({'rows':6,'groups':[{'label':'Boundary checks passed','value':1}],'total':1}))
'''
check('network-host-secrets-readonly-user-boundaries',probe,lambda x:validate_result(x['result']),3)
check('memory-limit','x=bytearray(512*1024*1024)\n',rejected,3)
check('excess-output','print("x"*(2*1024*1024))\n',lambda x: (len(x['stdout'])<=4096 or (_ for _ in ()).throw(AssertionError('logs unbounded'))),3)
check('symlink-artifact-rejected',"import os\nos.symlink('/etc/passwd','/work/result.json')\n",lambda x: (x['result'] is None or (_ for _ in ()).throw(AssertionError('symlink read'))),3)
process_probe='''import subprocess,sys
children=[]
try:
    while len(children)<80:
        children.append(subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']))
except OSError:
    print('process limit enforced')
finally:
    for child in children:
        child.kill()
        child.wait()
assert len(children)<80
'''
check('process-limit',process_probe,lambda x: (x['exit_code']==0 and 'process limit enforced' in x['stdout']) or (_ for _ in ()).throw(AssertionError('process limit failed')),3)
# Application job lifecycle and receipt recovery, also with the real runner.
jobs=Jobs(sandbox);lifecycles=[]
for containment in (False,True,False):
    planned=jobs.plan(CSV,SAMPLE_QUESTION,'sample');jobs.run(planned['id'],containment)
    end=time.monotonic()+25
    while jobs.get(planned['id'])['status']=='running' and time.monotonic()<end:time.sleep(.1)
    result=jobs.get(planned['id']);expected='contained' if containment else 'completed'
    assert result['status']==expected and result['receipt']['destroyed'],result
    assert 'csv' not in result and not jobs.active and not jobs.blocked
    lifecycles.append(result)
    print('job',expected,'passed',flush=True)
remaining=subprocess.run([sandbox.binary,'ps','-aq','--filter','label=org.figueira.sheetkeeper=prep'],capture_output=True,text=True,timeout=5).stdout.strip()
assert not remaining,'Orphan rehearsal containers remain'
report={'environment':'local Docker Desktop Linux VM; not Vultr; not rootless deployment proof','preflight':ready,'checks':records,'application_lifecycle':lifecycles,'orphan_containers':0,'complete':True,'paid_api_calls':0,'cloud_resources_activated':False}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('REAL_DOCKER_REHEARSAL_COMPLETE',len(records),'boundary/analysis cases and',len(lifecycles),'application lifecycles',flush=True)
