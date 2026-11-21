"""All tests use an isolated temporary enterprise database and synthetic data."""
import atexit
import os
import shutil
import tempfile

_runtime = tempfile.mkdtemp(prefix='companyagent-ci-v10-')
atexit.register(lambda: shutil.rmtree(_runtime, ignore_errors=True))
os.environ['COMPANYAGENT_RUNTIME_DIR'] = _runtime
os.environ['COMPANYAGENT_ADMIN_PASSWORD'] = 'CI-generated-isolated-password-ONLY'
os.environ['COMPANYAGENT_AUTO_SYNC'] = 'false'
os.environ.pop('B1X_API_KEY', None)  # Never call external model during CI.
