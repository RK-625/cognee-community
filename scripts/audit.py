import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
if ROOT.name=='scripts':ROOT=ROOT.parent
E=ROOT/'evidence'
def read(name):return json.loads((E/name).read_text())
def result(step):return read(step+'-result.json')
def rows(step,when='after'):
    snapshot=read(step+'-'+when+'-sql.json')
    return {r['id']:r for db,tables in snapshot.items() if db.startswith('dlt_database_') and not db.endswith('_staging') for table,records in tables.items() if table=='azure_blob_documents' for r in records}
def memory(step):return read(step+'-memory.json')
def stored(step):
    m=memory(step)
    return json.dumps([m['nodes'],m['edges'],m['vector_rows']],ensure_ascii=False).lower()
def downloaded(step):return [r['name'] for r in result(step)['downloads']]
def find(step,name):return next(r for r in rows(step).values() if r['title']==name)
checks=[]
def check(name,condition,detail):
    checks.append({'check':name,'passed':bool(condition),'detail':detail})

r=result('01-initial');initial=rows('01-initial')
check('Initial sync: seven eligible text documents',r['status']=='completed' and len(initial)==7 and len(r['downloads'])==7,r['counts'])
check('Exact size boundaries / empty / Unicode',len(find('01-initial','docs/at-limit.txt')['content'].encode())==1024 and len(find('01-initial','docs/below-limit.txt')['content'].encode())==1023 and find('01-initial','docs/empty.txt')['content']=='' and 'café' in find('01-initial','docs/unicode.txt')['content'],'1023/1024 accepted, 1025 excluded; empty content and Unicode preserved')
check('Prefix exclusion and folder skip',all('/docs/' in k for k in initial) and not any('above-limit' in k or k.endswith('/') for k in initial),'outside-prefix.txt and folder placeholder absent from staging')
check('Persistent new-process unchanged rerun',downloaded('02-unchanged')==[] and {k:v['content'] for k,v in rows('02-unchanged').items()}=={k:v['content'] for k,v in initial.items()},result('02-unchanged')['counts'])
check('Overwrite: one download, stable source URL ID',downloaded('03-update')==['docs/update-me.txt'] and find('01-initial','docs/update-me.txt')['id']==find('03-update','docs/update-me.txt')['id'] and 'Friday' in find('03-update','docs/update-me.txt')['content'],result('03-update').get('search'))
check('Overwrite removes old graph/vector fact','monday' not in stored('03-update'),'Current graph and stored vector text contain no Monday fact. Cognee recreates the content-derived Data ID; source URL ID stays stable.')
check('Delete: direct BlobNotFound and cleanup',len(rows('04-delete'))==6 and 'zephyr' not in stored('04-delete') and any(e.get('code')=='StorageErrorCode.BLOB_NOT_FOUND' or e.get('code')=='BlobNotFound' for e in result('04-delete')['sdk_events']),result('04-delete').get('search'))
check('Add plus newly oversized cleanup',downloaded('05-add-oversize')==['docs/new-document.txt'] and len(rows('05-add-oversize'))==6 and 'calypso' not in stored('05-add-oversize'),result('05-add-oversize').get('search'))
before=find('05-add-oversize','docs/unicode.txt');after=find('06-metadata','docs/unicode.txt');mutation=read('mutation-metadata.json')['events'][0]
check('Metadata: changed ETag / Last-Modified, identical content',downloaded('06-metadata')==['docs/unicode.txt'] and before['content']==after['content'] and before['id']==after['id'] and mutation['before']['etag']!=mutation['after']['etag'] and mutation['before']['last_modified']!=mutation['after']['last_modified'],mutation)
check('Metadata: no duplicate Data or graph artifacts',result('06-metadata')['counts']['data']==6 and memory('06-metadata')['nodes']==memory('05-add-oversize')['nodes'],'Six Data rows retained; graph node snapshot identical')
check('Fresh destination: complete independent snapshot',len(rows('07-fresh'))==6 and len(downloaded('07-fresh'))==6 and result('07-fresh')['pipeline_name']!=result('06-metadata')['pipeline_name'] and {k:v['content'] for k,v in rows('07-fresh').items()}=={k:v['content'] for k,v in rows('06-metadata').items()},result('07-fresh')['counts'])
check('Count guard: zero downloads and committed SQL unchanged',result('08-count-guard')['status']!='completed' and downloaded('08-count-guard')==[] and read('08-count-guard-before-sql.json')==read('08-count-guard-after-sql.json'),'8 non-folder blobs exceeds max_objects=7; committed staging and Data unchanged')
check('Count guard: cursor unchanged',read('08-count-guard-pipeline-state.json')[0]['state']['sources']==read('06-metadata-pipeline-state.json')[0]['state']['sources'],'Persisted inventory unchanged after expected failure')
check('Count guard: recovery succeeds without downloads',result('08-count-recovery')['status']=='completed' and downloaded('08-count-recovery')==[] and len(rows('08-count-recovery'))==6,result('08-count-recovery')['counts'])
if (E/'09-final-after-result.json').exists():
    b=result('09-final-before');a=result('09-final-after');c=a.get('counts',{})
    check('Final document: nonempty before, entirely empty after',b['counts']['data']==1 and b['counts']['nodes']>0 and b['counts']['edges']>0 and len(rows('09-final-after'))==0 and c.get('data')==0 and c.get('nodes')==0 and c.get('edges')==0 and bool(c.get('vectors')) and all(n==0 for n in c['vectors'].values()),{'before':b['counts'],'after':c})
    check('Final empty dataset search',a.get('search',{}).get('exception')=='NoDataError',a.get('search'))
extra=read('10-extra-live.json')
check('Live format, paging, race, and failure recovery assertions',extra.get('assertions')=='passed',{'accepted_formats':len(extra['formats']['after']['rows']),'pages':sum(e['op']=='page' for e in extra['formats']['events']),'race':extra['etag_race']['status'],'recovery':extra['race_recovery']['status'],'missing_container':extra['missing_container']['status'],'vanish':extra['vanish_after_listing']['status']})
hashes={r['source_sha256'] for p in E.glob('*-result.json') for r in [json.loads(p.read_text())]}
check('One tested connector source throughout',len(hashes)==1 and next(iter(hashes))==hashlib.sha256((E/'tested-azure_blob.py').read_bytes()).hexdigest(),list(hashes))
output={'status':'passed' if all(c['passed'] for c in checks) else 'failed','checks':checks}
(E/'validation-audit.json').write_text(json.dumps(output,indent=2,default=str))
for c in checks:print(('PASS' if c['passed'] else 'FAIL'),c['check'])
if output['status']=='failed':raise SystemExit(1)
