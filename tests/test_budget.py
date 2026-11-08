import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sheetkeeper.budget import budget_status, reserve_attempt, EXHAUSTED, UNAVAILABLE
from sheetkeeper.planner import infer


class PersistentBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "attempts.json"
        self.env = patch.dict(os.environ, {
            'SHEETKEEPER_ENABLE_INFERENCE': '1',
            'VULTR_INFERENCE_API_KEY': 'fake-test-key',
            'VULTR_INFERENCE_MODEL': 'fake-test-model',
            'SHEETKEEPER_INFERENCE_BUDGET_FILE': str(self.path),
            'SHEETKEEPER_INFERENCE_MAX_CALLS': '2',
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_status_never_initializes_or_exposes_private_path(self):
        status = budget_status()
        self.assertEqual((status['used'], status['remaining']), (0, 2))
        self.assertFalse(self.path.exists())
        self.assertNotIn(str(self.path), json.dumps(status))

    def test_reservations_survive_process_restart_and_limit_reduction(self):
        reserve_attempt()
        command = [sys.executable, '-c',
                   'from sheetkeeper.budget import reserve_attempt; reserve_attempt()']
        result = subprocess.run(command, capture_output=True, check=False, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(budget_status()['used'], 2)
        with self.assertRaisesRegex(ValueError, EXHAUSTED):
            reserve_attempt()
        with patch.dict(os.environ, {'SHEETKEEPER_INFERENCE_MAX_CALLS': '1'}):
            with self.assertRaisesRegex(ValueError, EXHAUSTED):
                reserve_attempt()
        self.assertEqual(json.loads(self.path.read_text())['calls'], 2)

    def test_concurrent_requests_cannot_overspend_the_count(self):
        # Initialize before contention; all subsequent reservations open their own fd.
        reserve_attempt()
        def attempt(_):
            try:
                reserve_attempt()
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(12))), 1)
        self.assertEqual(budget_status()['used'], 2)

    def test_timeouts_are_charged_before_network_and_never_refunded(self):
        def timeout(*args, **kwargs):
            self.assertGreaterEqual(json.loads(self.path.read_text())['calls'], 1)
            raise TimeoutError()
        with patch('urllib.request.urlopen', side_effect=timeout) as network:
            for _ in range(2):
                with self.assertRaises(ValueError):
                    infer([])
            with self.assertRaisesRegex(ValueError, EXHAUSTED):
                infer([])
        self.assertEqual(network.call_count, 2)
        self.assertEqual(budget_status()['remaining'], 0)

    def test_corrupt_counters_fail_closed_without_network(self):
        for raw in ('', '{}', '{"version":1,"calls":-1}',
                    '{"version":1,"calls":false}', '{"version":1,"calls":501}',
                    'x' * 4097):
            self.path.write_text(raw)
            with self.subTest(raw=raw[:60]), patch('urllib.request.urlopen') as network:
                with self.assertRaisesRegex(ValueError, UNAVAILABLE):
                    infer([])
                network.assert_not_called()
                self.assertFalse(budget_status()['ready'])

    def test_missing_invalid_settings_and_symlinks_fail_closed(self):
        for values in ({'SHEETKEEPER_INFERENCE_BUDGET_FILE': ''},
                       {'SHEETKEEPER_INFERENCE_BUDGET_FILE': 'relative.json'},
                       {'SHEETKEEPER_INFERENCE_MAX_CALLS': 'unlimited'},
                       {'SHEETKEEPER_INFERENCE_MAX_CALLS': '0'},
                       {'SHEETKEEPER_INFERENCE_MAX_CALLS': '501'}):
            with self.subTest(values=values), patch.dict(os.environ, values), patch('urllib.request.urlopen') as network:
                with self.assertRaisesRegex(ValueError, UNAVAILABLE):
                    infer([])
                network.assert_not_called()
        target = Path(self.temp.name) / 'other.json'
        target.write_text('{"version":1,"calls":0}')
        self.path.symlink_to(target)
        with patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, UNAVAILABLE):
                infer([])
            network.assert_not_called()
        self.assertEqual(json.loads(target.read_text())['calls'], 0)


if __name__ == '__main__':
    unittest.main()
