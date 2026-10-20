import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import sqlite3
import time
from datetime import datetime, UTC
from pathlib import Path
from bootstrap import ROOT, PACKAGE, configure, redact, service, CONTAINER

p=argparse.ArgumentParser()
p.add_argument('step');p.add_argument('--scope',default='main');p.add_argument('--prefix',default='docs/')
p.add_argument('--max-objects',type=int,default=12);p.add_argument('--question',default='When is the Kestrel launch?')
p.add_argument('--no-search',action='store_true');p.add_argument('--expect-failure',action='store_true')
args=p.parse_args();runtime=configure(args.scope)
events=[]

def dump(path,data):
    (ROOT/'evidence'/path).write_text(redact(json.dumps(data,default=str,indent=2)))

class Blob:
    def __init__(self,real,name):self.real=real;self.name=name
    def get_blob_properties(self,**kw):
        event={'operation':'get_blob_properties','name':self.name};events.append(event)
        try:return self.real.get_blob_properties(**kw)
        except Exception as exc:
            event.update(error=type(exc).__name__,code=str(getattr(exc,'error_code',None)));raise
    def download_blob(self,**kw):
        event={'operation':'download_blob','name':self.name,'etag':kw.get('etag'),'condition':str(kw.get('match_condition'))};events.append(event)
        try:
            real=self.real.download_blob(**kw)
        except Exception as exc:
            event.update(error=type(exc).__name__,code=str(getattr(exc,'error_code',None)));raise
        class Reader:
            def readall(self):
                data=real.readall();event.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest());return data
        return Reader()

class Container:
    def __init__(self,real):self.real=real
    def list_blobs(self,**kw):
        event={'operation':'list_blobs','prefix':kw.get('name_starts_with'),'objects':[]};events.append(event)
        for b in self.real.list_blobs(**kw):
            event['objects'].append({'name':b.name,'size':b.size,'etag':b.etag,'last_modified':str(b.last_modified)})
            yield b
        event['complete']=True
    def get_blob_client(self,name):return Blob(self.real.get_blob_client(name),name)

class Client:
    def __init__(self,real):self.real=real;self.url=real.url
    def get_container_client(self,name):return Container(self.real.get_container_client(name))

def sql_snapshot():
    result={}
    for file in (runtime/'system/databases').glob('*'):
        if not file.is_file() or file.name.endswith(('-wal','-shm')):continue
        try:
            with sqlite3.connect(f'file:{file}?mode=ro',uri=True) as conn:
                conn.row_factory=sqlite3.Row
                tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                wanted=[t for t in tables if 'azure_blob_documents' in t or t=='data' or t=='_dlt_pipeline_state']
                if wanted:
                    result[file.name]={t:[dict(r) for r in conn.execute('SELECT * FROM "'+t.replace('"','""')+'"')] for t in wanted}
        except sqlite3.DatabaseError:pass
    return result

async def memory_snapshot(dataset_name):
    from cognee.modules.data.methods import get_datasets
    from cognee.modules.data.methods.get_dataset_data import get_dataset_data
    from cognee.modules.users.methods import get_default_user
    from cognee.context_global_variables import set_database_global_context_variables
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.infrastructure.databases.vector.config import get_vectordb_context_config
    user=await get_default_user()
    dataset=next((d for d in await get_datasets(user.id) if d.name==dataset_name),None)
    if not dataset:return {'data':[],'nodes':[],'edges':[],'vector_counts':{}}
    rows=await get_dataset_data(dataset.id)
    data=[{col.name:getattr(r,col.name) for col in r.__table__.columns} for r in rows]
    async with set_database_global_context_variables(dataset.id,user.id):
        nodes,edges=await (await get_graph_engine()).get_graph_data()
        config=get_vectordb_context_config()
        import lancedb
        connection=lancedb.connect(config['vector_db_url'])
        names=connection.table_names()
        vectors={};counts={}
        for name in names:
            table=connection.open_table(name);counts[name]=table.count_rows()
            vectors[name]=[{k:v for k,v in r.items() if k!='vector'} for r in table.to_arrow().to_pylist()]
    return {'dataset_id':str(dataset.id),'data':data,'nodes':nodes,'edges':edges,'vector_counts':counts,'vector_rows':vectors}

async def main():
    import cognee
    import cognee_community_connector_azure_blob.azure_blob as module
    from cognee.tasks.ingestion.dlt_utils import pipeline_name_for_source
    from cognee_community_connector_azure_blob import azure_blob_source
    dataset='azure_validation_'+args.scope
    result={'step':args.step,'started':datetime.now(UTC).isoformat(),'scope':args.scope,'prefix':args.prefix,'dataset':dataset,'max_object_size':1024,'max_objects':args.max_objects,'source_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),'versions':{p:importlib.metadata.version(p) for p in ['cognee','dlt','fastembed','azure-storage-blob']}}
    dump(args.step+'-before-sql.json',sql_snapshot())
    with service() as real:
        result['azure_inventory']=[{'name':b.name,'size':b.size,'etag':b.etag,'last_modified':b.last_modified} for b in real.get_container_client(CONTAINER).list_blobs()]
        module._build_client=lambda *a: OwnedClient(real)
        source=azure_blob_source(CONTAINER,args.prefix,max_objects=args.max_objects,max_object_size=1024)
        result['pipeline_name']=pipeline_name_for_source(source,dataset)
        started=time.monotonic()
        try:
            response=await cognee.remember(source,dataset_name=dataset,primary_key='id',write_disposition='merge',max_rows_per_table=0,run_in_background=False,self_improvement=False)
            result['status']=response.status;result['error']=redact(response.error) if response.error else None
        except Exception as exc:
            result['status']='raised';result['error']=redact(exc);result['exception']=type(exc).__name__
        result['duration_seconds']=round(time.monotonic()-started,3)
    result['sdk_events']=events
    result['downloads']=[e for e in events if e['operation']=='download_blob']
    dump(args.step+'-after-sql.json',sql_snapshot())
    states=[]
    for file in runtime.rglob('state.json'):
        try:states.append({'path':str(file.relative_to(runtime)),'state':json.loads(file.read_text())})
        except Exception:pass
    dump(args.step+'-pipeline-state.json',states)
    dump(args.step+'-result.json',result)
    try:
        memory=await memory_snapshot(dataset);dump(args.step+'-memory.json',memory)
        result['counts']={'data':len(memory['data']),'nodes':len(memory['nodes']),'edges':len(memory['edges']),'vectors':memory['vector_counts']}
    except Exception as exc:result['snapshot_error']=redact(exc)
    if not args.no_search and result['status']=='completed':
        try:
            answer=await cognee.search(query_text=args.question,query_type=cognee.SearchType.GRAPH_COMPLETION,datasets=[dataset])
            result['search']={'question':args.question,'answer':answer}
        except Exception as exc:result['search']={'question':args.question,'exception':type(exc).__name__,'error':redact(exc)}
    result['finished']=datetime.now(UTC).isoformat();dump(args.step+'-result.json',result)
    print('RESULT',args.step,result['status'],'downloads',len(result['downloads']),'counts',result.get('counts'),'snapshot_error',result.get('snapshot_error'),flush=True)
    if not args.expect_failure and result['status']!='completed':raise SystemExit(1)

class OwnedClient(Client):
    def __enter__(self):return self
    def __exit__(self,*args):return None

asyncio.run(main())
