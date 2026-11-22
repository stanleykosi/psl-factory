"""Run individually specified design assertions against the mounted API."""

from collections import Counter, defaultdict
import json
import os
import unittest

from .api_contract_runner import ContractRunner
from .api_state_plan import MARKER, pending_plan, read_plan


class StateReplayRunner(ContractRunner):
    active_test = None

    def record_response(self, identity, status):
        if self.active_test is not None:
            self.responses[self.active_test][f'{identity}:{status}'] += 1

    def get_resultclass(self):
        replay = self

        class CaseResult(unittest.TextTestResult):
            def startTest(self, test):
                replay.active_test = test.id()
                super().startTest(test)

            def addSuccess(self, test):
                replay.passed.add(test.id())
                super().addSuccess(test)

            def stopTest(self, test):
                replay.active_test = None
                super().stopTest(test)

        return CaseResult

    def run_tests(self, test_labels, **kwargs):
        if self.parallel > 1:
            raise ValueError('State replays run one reporting process per isolated database.')
        suite = os.environ['PSL_DESIGN_TEST_GROUP']
        _, plan = read_plan()
        if os.environ.get('PSL_API_REPLAY_PENDING') == '1':
            plan = pending_plan(plan)
        selected = [row for row in plan if row['suite'] == suite]
        if not selected or set(test_labels) != {row['test'] for row in selected}:
            raise ValueError('The selected tests must equal the manifest for this replay suite.')
        self.responses = defaultdict(Counter)
        self.passed = set()
        result = super().run_tests(test_labels, **kwargs)
        failed = 0
        for row in selected:
            observed = self.responses[row['test']]
            missing = Counter(row['required_responses'].split()) - observed
            status = 'passed' if row['test'] in self.passed and not missing else 'failed'
            failed += status == 'failed'
            print(MARKER + json.dumps({
                **row, 'result': status, 'observed': sorted(observed.items()),
                'missing': sorted(missing.items()), 'deployment': os.getenv('RAILWAY_DEPLOYMENT_ID', ''),
                'revision': os.getenv('PSL_API_STATE_REVISION', ''),
            }, separators=(',', ':')), flush=True)
        return max(result, failed)
