import asyncio
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, UTC
from bootstrap import ROOT, PACKAGE, WORKTREE, configure, redact, service, CONTAINER

configure('preflight')
result = {'time': datetime.now(UTC).isoformat(), 'python': platform.python_version(), 'versions': {p: importlib.metadata.version(p) for p in ['cognee','dlt','fastembed','azure-core','azure-storage-blob']}}
result['commit'] = subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],text=True).strip()
result['source_sha256'] = hashlib.sha256((PACKAGE/'cognee_community_connector_azure_blob/azure_blob.py').read_bytes()).hexdigest()
(ROOT/'evidence/source.diff').write_bytes(subprocess.check_output(['git','-C',str(WORKTREE),'diff']))
try:
    with service() as client:
        container=client.get_container_client(CONTAINER)
        result['container']={'name':CONTAINER,'exists':container.exists(),'blobs':[b.name for b in container.list_blobs()]}
    print('AZURE: read/list authentication successful', flush=True)
except Exception as exc:
    result['azure_error']=redact(exc)
    print('AZURE:', type(exc).__name__, redact(exc), flush=True)

async def models():
    import os
    from cognee.infrastructure.databases.vector.embeddings.FastembedEmbeddingEngine import FastembedEmbeddingEngine
    engine=FastembedEmbeddingEngine(model='BAAI/bge-small-en-v1.5',dimensions=384)
    vectors=await engine.embed_text(['Azure connector validation.'])
    result['embedding']={'dimensions':len(vectors[0]),'nonzero':any(vectors[0]),'tokens':vectors.tokens}
    print('EMBEDDING: local nonzero vector confirmed',flush=True)
    import litellm
    response=await litellm.acompletion(model=os.environ['LLM_MODEL'],api_base=os.environ['LLM_ENDPOINT'],api_key=os.environ['LLM_API_KEY'],messages=[{'role':'user','content':'Reply with exactly Azure validation ready.'}],max_tokens=50,timeout=45)
    result['llm']={'model':os.environ['LLM_MODEL'],'provider':os.environ['LLM_PROVIDER'],'response':response.choices[0].message.content,'usage':response.usage.model_dump()}
    print('LLM:', result['llm']['response'],flush=True)

try:
    asyncio.run(models())
except Exception as exc:
    result['model_error']=redact(exc)
    print('MODEL:',type(exc).__name__,redact(exc),flush=True)
(ROOT/'evidence/preflight-success.json').write_text(json.dumps(result,indent=2))
