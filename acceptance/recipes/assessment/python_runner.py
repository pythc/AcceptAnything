"""Record the standard unittest runner's individual outcomes without changing tests."""
import importlib.util
import json
import sys
import time
import unittest
spec = importlib.util.spec_from_file_location('acceptance_upload_tests', '/workspace/tests/upload-helper.test.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class Result(unittest.TextTestResult):
    records = []
    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)
    def record(self, test, status, detail=''):
        self.records.append({'name': test.id().split('.', 1)[1], 'status': status, 'detail': detail, 'duration': time.monotonic()-self.started})
    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, 'passed')
    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, 'failed', self._exc_info_to_string(err, test))
    def addError(self, test, err):
        super().addError(test, err); self.record(test, 'error', self._exc_info_to_string(err, test))
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, 'skipped', reason)
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
if len(sys.argv) > 1:
    planned = json.loads(sys.argv[1])
    def flatten(node):
        for test in node:
            if isinstance(test, unittest.TestSuite): yield from flatten(test)
            else: yield test
    available = {t.id().split('.', 1)[1]: t for t in flatten(suite)}
    if len(set(planned)) != len(planned) or any(name not in available for name in planned):
        raise ValueError('Frozen Python test selection does not match available tests')
    suite = unittest.TestSuite(available[name] for name in planned)
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, resultclass=Result).run(suite)
print(json.dumps({'runner': 'unittest', 'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped), 'cases': result.records}))
sys.exit(0 if result.wasSuccessful() else 1)
