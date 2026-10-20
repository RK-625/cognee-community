import copy
import hashlib
import json
from datetime import datetime, UTC
from bootstrap import ROOT, configure, service, CONTAINER, redact

runtime=configure('extra')
import dlt
from cognee_community_connector_azure_blob import azure_blob_source

events=[]
class B:
    def __init__(self,blob,owner):self.blob=blob;self.owner=owner
    def download_blob(self,**kw):
        e={'op':'download','name':self.blob.blob_name,'etag':kw.get('etag'),'condition':str(kw.get('match_condition'))};events.append(e)
        if self.owner.mutate:
            action=self.owner.mutate;self.owner.mutate=None
            if action=='overwrite':self.blob.upload_blob(b'The Iris beacon code is silver crane.\n',overwrite=True)
            if action=='vanish':self.blob.delete_blob()
            e['mutation_before_download']=action
        try:r=self.blob.download_blob(**kw)
        except Exception as exc:e['error']=type(exc).__name__;e['code']=str(getattr(exc,'error_code',None));raise
        class Reader:
            def readall(self):
                data=r.readall();e['bytes']=len(data);return data
        return Reader()
    def get_blob_properties(self):
        e={'op':'properties','name':self.blob.blob_name};events.append(e)
        try:return self.blob.get_blob_properties()
        except Exception as exc:e['error']=type(exc).__name__;e['code']=str(getattr(exc,'error_code',None));raise

class C:
    def __init__(self,client,mutate=None,paged=False):self.real=client;self.url=client.url;self.mutate=mutate;self.paged=paged
    def get_container_client(self,name):
        real=self.real.get_container_client(name);owner=self
        class Container:
            def list_blobs(self,**kw):
                listing=real.list_blobs(**kw,results_per_page=2) if owner.paged else real.list_blobs(**kw)
                if owner.paged:
                    for i,page in enumerate(listing.by_page()):
                        objects=list(page);events.append({'op':'page','index':i,'names':[b.name for b in objects]});yield from objects
                else:yield from listing
            def get_blob_client(self,name):return B(real.get_blob_client(name),owner)
        return Container()

def pipeline(name):
    return dlt.pipeline(pipeline_name='live_'+name,destination=dlt.destinations.sqlalchemy(f'sqlite:///{runtime / (name+".db")}'),dataset_name=name,pipelines_dir=str(runtime/'pipelines'))

def snapshot(p):
    try:
        with p.sql_client() as c,c.execute_query('SELECT id, content FROM azure_blob_documents') as cursor:rows=dict(cursor.fetchall())
    except Exception:rows={}
    state=copy.deepcopy(p.state.get('sources',{}))
    return {'rows':rows,'state':state}

def run(p,client,prefix,container=CONTAINER):
    start=len(events)
    try:
        info=p.run(azure_blob_source(container,prefix,client=client,max_objects=30,max_object_size=1024),write_disposition='merge')
        status='completed' if not info.has_failed_jobs else 'failed-jobs';error=None
    except Exception as exc:status='failed';error=redact(exc)
    return {'status':status,'error':error,'events':events[start:],'after':snapshot(p)}

result={'time':datetime.now(UTC).isoformat(),'coverage':'real Azure SDK with controlled mutation immediately before conditional download; real SQLite dlt destination'}
import atexit
atexit.register(lambda: (ROOT/'evidence/10-extra-live.json').write_text(redact(json.dumps(result,indent=2,default=str))))
with service() as real:
    formats=pipeline('formats');r=run(formats,C(real,paged=True),'formats/');result['formats']=r
    assert r['status']=='completed'
    assert len(r['after']['rows'])==15
    assert len([e for e in r['events'] if e['op']=='download'])==15
    assert all('skip.pdf' not in uri and 'noextension' not in uri for uri in r['after']['rows'])
    assert any(text=='BOM decoded without marker.' for text in r['after']['rows'].values())
    assert any('\ufffd' in text for text in r['after']['rows'].values())
    race=pipeline('race');c=C(real)
    result['race_initial']=run(race,c,'race/');before=snapshot(race)
    real.get_blob_client(CONTAINER,'race/document.txt').upload_blob(b'The Iris beacon code is copper lark.\n',overwrite=True)
    result['etag_race']=run(race,C(real,mutate='overwrite'),'race/')
    assert result['etag_race']['status']=='failed'
    assert result['etag_race']['after']==before
    result['race_recovery']=run(race,C(real),'race/')
    assert result['race_recovery']['status']=='completed'
    assert any('silver crane' in t for t in result['race_recovery']['after']['rows'].values())
    before=snapshot(race)
    result['missing_container']=run(race,C(real),'race/',container='cognee-validation-missing')
    assert result['missing_container']['status']=='failed'
    assert result['missing_container']['after']==before
    real.get_blob_client(CONTAINER,'race/document.txt').upload_blob(b'The Iris beacon code is amber tern.\n',overwrite=True)
    result['vanish_after_listing']=run(race,C(real,mutate='vanish'),'race/')
    assert result['vanish_after_listing']['status']=='completed'
    assert result['vanish_after_listing']['after']['rows']=={}
result['assertions']='passed'
(ROOT/'evidence/10-extra-live.json').write_text(redact(json.dumps(result,indent=2,default=str)))
print('EXTRA LIVE: formats, real pagination, ETag race rollback/recovery, missing-container rollback, disappearance passed')
