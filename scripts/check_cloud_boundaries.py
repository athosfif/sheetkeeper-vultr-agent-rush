"""Audit the existing Vultr runtime using fixed synthetic code; no inference.

Separate from the 1 October local rehearsal. Run as the controller's non-root
service user with its rootless Docker socket. Never puts credentials in workers.
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time

from sheetkeeper.contracts import validate_result
from sheetkeeper.jobs import Jobs
from sheetkeeper.planner import SAMPLE_CODE, SAMPLE_QUESTION
from sheetkeeper.sandbox import DockerSandbox

ROOT = Path(__file__).resolve().parents[1]
CSV = (ROOT / "fixtures/sales.csv").read_text()

BOUNDARY_PROBE = '''import json, os, socket
from pathlib import Path
assert os.getuid() == 10001
assert not Path('/var/run/docker.sock').exists()
assert not Path('/Users/athvs').exists()
assert not Path('/Volumes/FIGUEIRA').exists()
assert not Path('/opt/sheetkeeper').exists()
assert not Path('/etc/sheetkeeper.env').exists()
assert not any(k in os.environ for k in ('VULTR_INFERENCE_API_KEY','SHEETKEEPER_ACCESS_CODE','AWS_SECRET_ACCESS_KEY'))
try:
    Path('/root-write-probe').write_text('x')
except OSError: pass
else: raise AssertionError('root filesystem writable')
# Kernel interface readback tests network isolation without attempting egress.
interfaces = sorted(name for _, name in socket.if_nameindex())
assert interfaces == ['lo'], interfaces
assert not Path('/proc/net/route').read_text().splitlines()[1:]
limits = {name: Path('/sys/fs/cgroup', name).read_text().strip()
          for name in ('cpu.max', 'memory.max', 'pids.max')}
quota, period = map(int, limits['cpu.max'].split())
assert quota > 0 and quota == period, limits
assert int(limits['memory.max']) == 256 * 1024 * 1024, limits
assert int(limits['pids.max']) == 64, limits
print(json.dumps({'cgroup_readback': limits, 'interfaces': interfaces,
                  'uid': os.getuid(), 'network_egress_attempted': False}))
Path('/work/result.json').write_text(json.dumps({'rows':6,'groups':[{'label':'Boundary checks passed','value':1}],'total':1}))
'''

PROCESS_PROBE = '''import os, signal, time
children = []
try:
    while len(children) < 80:
        pid = os.fork()
        if pid == 0:
            time.sleep(30)
            os._exit(0)
        children.append(pid)
except OSError:
    print('process limit enforced')
finally:
    for pid in children:
        try: os.kill(pid, signal.SIGKILL)
        except ProcessLookupError: pass
    for pid in children: os.waitpid(pid, 0)
assert len(children) < 80
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(os.environ.get('SHEETKEEPER_CLOUD_REPORT',
                                                    '/var/lib/sheetkeeper/cloud-boundaries.json')))
    args = parser.parse_args()
    output_path = args.output.resolve()
    if (not args.output.is_absolute()
            or output_path.name == 'docker-rehearsal-20261001.json'):
        parser.error('Use an absolute output path separate from the October rehearsal.')
    if platform.system() != 'Linux' or os.geteuid() == 0:
        parser.error('Run on Linux as the unprivileged controller service user.')
    if os.environ.get('SHEETKEEPER_DEPLOYMENT_PROVIDER') != 'vultr':
        parser.error('Expected the existing controller deployment configuration for Vultr.')
    os.environ['SHEETKEEPER_ENABLE_INFERENCE'] = '0'  # this process only; fixed audit mode
    report = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'audit_mode': 'fixed_synthetic_fixture_no_inference',
        'code_origin': 'Prepared 2026-10-01; cloud audit adaptation 2026-11-08',
        'cloud_provider': 'vultr',
        'cloud_provider_source': 'controller environment; independently verify console deployment receipt',
        'environment': {'os': platform.system(), 'kernel': platform.release(),
                        'architecture': platform.machine(), 'controller_uid': os.geteuid()},
        'provider_api_calls': 0,
        'cloud_resources_activated_by_this_audit': False,
        'checks': [], 'application_lifecycle': [], 'complete': False,
    }

    def save():
        # Atomic current-run report, private to the service user; no raw CSV/secrets.
        with tempfile.NamedTemporaryFile(mode='w', dir=output_path.parent,
                                         prefix='.cloud-audit-', delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, output_path)
            finally:
                temporary.unlink(missing_ok=True)

    sandbox = DockerSandbox()

    def check(name, code, expectation, timeout=3):
        result = sandbox.execute(code, CSV, timeout)
        inspected = subprocess.run([sandbox.binary, 'container', 'inspect', result['container']],
                                   capture_output=True, text=True, timeout=5)
        # A generic Docker connection/permission error does not prove removal.
        gone = inspected.returncode != 0 and 'No such container' in inspected.stderr
        result['removal_independently_checked'] = gone
        report['checks'].append({'case': name, 'output': result})
        save()
        assert result['destroyed'] and gone, (name, 'container removal not verified')
        expectation(result)
        print(name, 'passed', result['elapsed_ms'], 'ms', flush=True)
        return result

    def normal(result):
        actual = validate_result(result['result'])
        expected = defaultdict(float)
        for row in csv.DictReader(CSV.splitlines()):
            expected[row['channel']] += float(row['revenue'])
        assert actual['rows'] == 6 and actual['total'] == sum(expected.values())
        assert {group['label']: group['value'] for group in actual['groups']} == dict(expected)
        assert result['exit_code'] == 0 and not result['timed_out']

    def contained(result):
        assert result['timed_out'] and result['result'] is None

    def rejected(result):
        assert result['exit_code'] != 0 and result['result'] is None

    def boundaries(result):
        validate_result(result['result'])
        assert result['exit_code'] == 0 and not result['timed_out']
        report['kernel_limits_inside_container'] = json.loads(result['stdout'])
        save()

    def excess_output(result):
        assert result['result'] is None and len(result['stdout']) <= 4096

    def symlink_rejected(result):
        assert result['result'] is None

    def processes_limited(result):
        assert result['exit_code'] == 0 and 'process limit enforced' in result['stdout']

    try:
        ready = sandbox.preflight()
        report['preflight'] = ready
        assert ready['ready'], ready
        raw = subprocess.run([sandbox.binary, 'info', '--format', '{{json .}}'],
                             capture_output=True, text=True, timeout=5, check=True)
        details = json.loads(raw.stdout)
        report['docker'] = {key: details.get(key) for key in
                            ('ServerVersion', 'OSType', 'CgroupDriver', 'CgroupVersion',
                             'SecurityOptions', 'Warnings')}
        assert details['OSType'] == 'linux' and details['CgroupVersion'] == '2'
        assert details['CgroupDriver'] == 'systemd'
        assert any('rootless' in option for option in details['SecurityOptions'])
        assert not details.get('Warnings'), details.get('Warnings')
        save()
        check('normal-real-analysis', SAMPLE_CODE, normal, 15)
        check('infinite-loop-timeout', 'while True:\n    pass\n', contained, 3)
        check('recovery-after-timeout', SAMPLE_CODE, normal, 15)
        check('network-host-secrets-readonly-user-cgroup-boundaries', BOUNDARY_PROBE, boundaries, 3)
        check('memory-limit', 'x=bytearray(512*1024*1024)\n', rejected, 3)
        check('excess-output', 'print("x"*(2*1024*1024))\n', excess_output, 3)
        check('symlink-artifact-rejected', "import os\nos.symlink('/etc/passwd','/work/result.json')\n", symlink_rejected, 3)
        check('process-limit', PROCESS_PROBE, processes_limited, 3)
        jobs = Jobs(sandbox)
        for containment in (False, True, False):
            planned = jobs.plan(CSV, SAMPLE_QUESTION, 'sample')
            jobs.run(planned['id'], containment)
            deadline = time.monotonic() + 25
            while jobs.get(planned['id'])['status'] == 'running' and time.monotonic() < deadline:
                time.sleep(.1)
            result = jobs.get(planned['id'])
            expected_status = 'contained' if containment else 'completed'
            assert result['status'] == expected_status and result['receipt']['destroyed'], result
            assert 'csv' not in result and not jobs.active and not jobs.blocked
            report['application_lifecycle'].append(result)
            save()
            print('job', expected_status, 'passed', flush=True)
        remaining = subprocess.run([sandbox.binary, 'ps', '-aq', '--filter',
                                    'label=org.figueira.sheetkeeper=prep'], capture_output=True,
                                   text=True, timeout=5, check=True).stdout.strip()
        assert not remaining, 'SheetKeeper audit containers remain'
        report.update(complete=True, orphan_containers=0,
                      completed_at=datetime.now(timezone.utc).isoformat())
        save()
        print('CLOUD_BOUNDARY_AUDIT_COMPLETE', len(report['checks']),
              'fixed-code cases;', len(report['application_lifecycle']),
              'application lifecycles; 0 provider API calls', flush=True)
    except Exception as error:
        report['failure'] = {'type': type(error).__name__, 'message': str(error)[:2000]}
        save()
        raise


if __name__ == '__main__':
    main()
