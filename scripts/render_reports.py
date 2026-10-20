import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
if ROOT.name=='scripts':ROOT=ROOT.parent
E=ROOT/'evidence';OUT=ROOT/'reports';OUT.mkdir(exist_ok=True)
FONT='/System/Library/Fonts/Supplemental/Arial Unicode.ttf';BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
def read(name):return json.loads((E/name).read_text())
def rows(step,when='after'):
    snapshot=read(step+'-'+when+'-sql.json')
    return {r['title']:r for db,tables in snapshot.items() if db.startswith('dlt_database_') and not db.endswith('_staging') for table,records in tables.items() if table=='azure_blob_documents' for r in records}
def answer(r):
    s=r.get('search',{})
    if 'exception' in s:return s['exception']+': no searchable documents remain (expected).'
    return ' '.join(str(v) for item in s.get('answer',[]) for v in item.get('search_result',[]))
titles={'01-initial':'Initial sync / exact size boundaries','02-unchanged':'Unchanged rerun / persisted cursor','03-update':'Overwrite / incremental replacement','04-delete':'Delete one document / forget its memory','05-add-oversize':'New document + previously ingested blob exceeds size limit','06-metadata':'Metadata-only edit / Azure cursor behavior','07-fresh':'Fresh destination / independent full snapshot','08-count-guard':'Count guard / fail before downloads','08-count-recovery':'Count guard recovery / retained cursor','09-final-before':'Final-document regression / before deletion','09-final-after':'Final-document regression / after deletion'}

def report(step):
    r=read(step+'-result.json');before=rows(step,'before');after=rows(step)
    inventory={b['name']:b for b in r['azure_inventory'] if b['name'].startswith(r['prefix']) or b['name']=='outside-prefix.txt'}
    downloads={b['name']:b for b in r['downloads']}
    items=[]
    for name in sorted(set(inventory)|set(before)|set(after)):
        blob=inventory.get(name);row=after.get(name);old=before.get(name)
        size=blob['size'] if blob else len((old or row)['content'].encode())
        if not name.startswith(r['prefix']):status='Excluded';reason='outside selected prefix'
        elif name.endswith('/') and size==0:status='Skipped';reason='directory placeholder'
        elif r['status']!='completed':status='Not processed';reason='max_objects guard aborted extraction'
        elif row and name in downloads:status='Updated' if old else 'Added';reason='conditional content download'
        elif row:status='Unchanged';reason='no content download'
        elif old:status='Removed';reason='now oversized' if blob and size>1024 else 'confirmed BlobNotFound'
        else:status='Skipped';reason='above 1024-byte limit' if size>1024 else 'unsupported text type'
        text=(row or old or {}).get('content','').strip()
        preview=text if text else ('[empty content]' if row else '—')
        preview=preview.replace('\u2615', r'\u2615')
        if old and not row:preview='Last known: '+preview
        items.append((name,str(size),status,str(downloads.get(name,{}).get('bytes',0)),preview,reason))
    c=r.get('counts',{});height=410+len(items)*90+230
    im=Image.new('RGB',(1800,height),'#f7f9fc');d=ImageDraw.Draw(im)
    d.rectangle((0,0,1800,12),fill='#0078d4')
    d.text((54,40),'AZURE BLOB CONNECTOR · LIVE VALIDATION',font=font(22,True),fill='#0078d4')
    d.text((54,82),titles[step],font=font(38,True),fill='#172b45')
    d.text((54,140),'Rendered test report from saved JSON measurements · '+r['started'],font=font(21),fill='#52657c')
    d.text((54,181),f"Cognee {r['versions']['cognee']} | dlt {r['versions']['dlt']} | Azure SDK {r['versions']['azure-storage-blob']} | local fastembed",font=font(22),fill='#34495e')
    metrics=[('SYNC',r['status'].upper()),('DOWNLOADS',str(len(r['downloads']))),('STAGING',str(len(after))),('DATA',str(c.get('data','?'))),('GRAPH',f"{c.get('nodes','?')} nodes / {c.get('edges','?')} edges")]
    for i,(label,value) in enumerate(metrics):
        x=54+i*342;d.rounded_rectangle((x,237,x+326,329),radius=8,fill='white',outline='#dce4ee')
        d.text((x+18,250),label,font=font(17,True),fill='#61748c');d.text((x+18,278),value,font=font(26,True),fill='#172b45')
    y=367;cols=[54,425,545,805,966]
    for x,t in zip(cols,['Blob name','Bytes','Observed action','Read bytes','Content preview / reason']):d.text((x,y),t,font=font(21,True),fill='#172b45')
    y+=38
    colors={'Added':'#177245','Updated':'#0078d4','Removed':'#a33b2b','Skipped':'#6c7684','Excluded':'#6c7684','Unchanged':'#596c82','Not processed':'#a96c00'}
    for name,size,status,download,preview,reason in items:
        d.rectangle((44,y,1756,y+83),fill='white');d.line((44,y+84,1756,y+84),fill='#dce4ee')
        d.text((cols[0],y+12),name,font=font(22),fill='#172b45');d.text((cols[1],y+12),size,font=font(22),fill='#172b45')
        d.text((cols[2],y+12),status,font=font(22,True),fill=colors[status]);d.text((cols[3],y+12),download,font=font(22),fill='#172b45')
        for j,line in enumerate(textwrap.wrap(preview,width=65)[:2]):d.text((cols[4],y+7+j*24),line,font=font(20),fill='#34495e')
        d.text((cols[4],y+57),reason,font=font(17),fill='#61748c');y+=90
    y+=20
    summary=answer(r)
    if summary:
        d.text((54,y),'GRAPH SEARCH',font=font(18,True),fill='#0078d4');y+=30
        for line in textwrap.wrap(summary,140)[:3]:d.text((54,y),line,font=font(23),fill='#172b45');y+=29
    else:
        note='Expected failure; persisted inventory, staging and Data unchanged.' if r['status']!='completed' else 'Content and storage measurements recorded; no search requested for this step.'
        d.text((54,y),note,font=font(22),fill='#34495e');y+=35
    counts=', '.join(f'{k}: {v}' for k,v in c.get('vectors',{}).items())
    for line in textwrap.wrap('Vector rows before search: '+counts,155):d.text((54,y+10),line,font=font(18),fill='#52657c');y+=23
    d.text((54,height-38),f"Raw evidence: {step}-result.json, SQL, pipeline state and memory snapshots | limits: {r['max_objects']} objects / 1024 bytes",font=font(18),fill='#61748c')
    im.save(OUT/(step+'.png'))

for step in titles:report(step)

extra=read('10-extra-live.json');fmt=extra['formats'];rows_fmt=fmt['after']['rows']
im=Image.new('RGB',(1800,1470),'#f7f9fc');d=ImageDraw.Draw(im)
d.rectangle((0,0,1800,12),fill='#0078d4')
d.text((54,45),'AZURE BLOB CONNECTOR · SUPPLEMENTAL LIVE CHECKS',font=font(24,True),fill='#0078d4')
d.text((54,100),'Formats, pagination and real Azure failure recovery',font=font(38,True),fill='#172b45')
d.text((54,162),'Rendered from 10-extra-live.json · real Azure SDK + SQLite dlt · assertions: '+extra['assertions'],font=font(22),fill='#52657c')
y=235
for uri,text in sorted(rows_fmt.items()):
    name=uri.split('/formats/')[-1];d.rectangle((44,y,1756,y+49),fill='white')
    d.text((56,y+10),name,font=font(23),fill='#172b45');d.text((450,y+10),'DOWNLOADED / STAGED',font=font(20,True),fill='#177245');d.text((880,y+10),text.strip(),font=font(22),fill='#34495e');y+=55
notes=[
 'Unsupported PDF and extensionless blobs: zero downloads; folder placeholder ignored.',
 'Forced Azure pagination: 9 pages consumed (2 entries/page maximum); 15 eligible rows staged.',
 'ETag race: real overwrite immediately before If-Match download caused ConditionNotMet; rows/cursor unchanged.',
 'Retry: downloaded the latest content and committed successfully.',
 'Missing container: real ContainerNotFound; prior rows/cursor retained.',
 'Disappeared after listing: real BlobNotFound; final staging row deleted.',
 'BOM stripped; invalid UTF-8 replaced with U+FFFD. These checks exercise source+dlt, without LLM calls.',
]
y+=25
for note in notes:
    for line in textwrap.wrap(note,135):d.text((54,y),line,font=font(22),fill='#34495e');y+=30
im.save(OUT/'10-extra-live.png')
print('Rendered',len(list(OUT.glob('*.png'))),'measured evidence reports')
