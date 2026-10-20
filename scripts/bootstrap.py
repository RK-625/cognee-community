import os
import sys
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
if ROOT.name == 'scripts':
    ROOT = ROOT.parent
for directory in ['evidence', 'logs', 'fixtures', 'screenshots', 'reports', 'runtime']:
    (ROOT / directory).mkdir(exist_ok=True)
WORKTREE = Path(os.environ.get('AZURE_VALIDATION_WORKTREE', '/Users/apple/.codex/worktrees/06c1/cognee-community'))
PACKAGE = WORKTREE / 'packages/connector/azure-blob'
SECRETS = dotenv_values(WORKTREE / '.env')
for key, value in SECRETS.items():
    if value is not None:
        os.environ[key] = value
sys.path.insert(0, str(PACKAGE))

def configure(scope='main'):
    runtime = ROOT / 'runtime' / scope
    runtime.mkdir(parents=True, exist_ok=True)
    settings = {
        'SYSTEM_ROOT_DIRECTORY': str(runtime / 'system'),
        'DATA_ROOT_DIRECTORY': str(runtime / 'data'),
        'CACHE_ROOT_DIRECTORY': str(runtime / 'cache'),
        'LOGS_ROOT_DIRECTORY': str(ROOT / 'logs' / scope),
        'COGNEE_LOGS_DIR': str(ROOT / 'logs' / scope),
        'DLT_DATA_DIR': str(runtime / 'dlt'),
        'PIPELINES_DIR': str(runtime / 'pipelines'),
        'EMBEDDING_PROVIDER': 'fastembed',
        'EMBEDDING_MODEL': 'BAAI/bge-small-en-v1.5',
        'EMBEDDING_DIMENSIONS': '384',
        'FASTEMBED_CACHE_PATH': str(ROOT / 'runtime' / 'models'),
        'COGNEE_TRACING_ENABLED': 'false',
        'TELEMETRY_DISABLED': '1',
        'DLT_TELEMETRY': 'false',
        'VECTOR_DB_SUBPROCESS_ENABLED': 'false',
        'MOCK_EMBEDDING': 'false',
    }
    os.environ.update(settings)
    os.chdir(runtime)
    return runtime

def redact(text):
    text = str(text)
    for key, value in SECRETS.items():
        if value and ('KEY' in key or 'TOKEN' in key or 'SECRET' in key):
            text = text.replace(value, '[REDACTED]')
    return text

def service():
    from azure.storage.blob import BlobServiceClient
    return BlobServiceClient(os.environ['AZURE_STORAGE_ACCOUNT_URL'], credential=os.environ['AZURE_STORAGE_KEY'], retry_total=1, connection_timeout=15, read_timeout=30)

CONTAINER = 'cognee-validation'
