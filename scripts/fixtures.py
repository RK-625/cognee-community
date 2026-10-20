import hashlib
import json
import sys
from datetime import datetime, UTC
from bootstrap import ROOT, service, CONTAINER

def padded(text, size):
    content=text.encode()
    return content + b' ' * (size-len(content))

initial={
 'docs/at-limit.txt':padded('The Borealis archive opens at noon on Saturday.\n',1024),
 'docs/below-limit.txt':padded('The Meridian museum admission costs nine dollars.\n',1023),
 'docs/delete-me.txt':b'The Zephyr vault access phrase is amber compass.\n',
 'docs/empty.txt':b'',
 'docs/support.txt':b'The Calypso support desk opens at six AM.\n',
 'docs/unicode.txt':'The café mascot is a blue heron. ☕\n'.encode(),
 'docs/update-me.txt':b'The Kestrel launch is Monday at nine AM.\n',
 'docs/above-limit.txt':padded('Oversized excluded document.\n',1025),
 'docs/folder/':b'',
 'outside-prefix.txt':b'The excluded root marker is violet comet.\n',
}
action=sys.argv[1]
events=[]
with service() as client:
    c=client.get_container_client(CONTAINER)
    def upload(name,payload):
        # Refuse to replace preexisting fixtures on initial setup.
        c.upload_blob(name,payload,overwrite=(action!='initial'))
        path=ROOT/'fixtures'/name
        if not name.endswith('/'):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
        events.append({'action':'upload','name':name,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
    if action=='initial':
        for name,payload in initial.items():upload(name,payload)
    elif action=='update':upload('docs/update-me.txt',b'The Kestrel launch is Friday at three PM.\n')
    elif action=='delete':
        c.delete_blob('docs/delete-me.txt');events.append({'action':'delete','name':'docs/delete-me.txt'})
    elif action=='add-oversize':
        upload('docs/new-document.txt',b'The Polaris project mascot is a silver otter.\n')
        upload('docs/support.txt',padded('The Calypso support desk opens at six AM.\n',1115))
    elif action=='metadata':
        b=c.get_blob_client('docs/unicode.txt');before=b.get_blob_properties()
        b.set_blob_metadata({'validation':'metadata-only','scenario':'azure-cursor'})
        after=b.get_blob_properties()
        events.append({'action':'metadata','name':b.blob_name,'before':{'etag':before.etag,'last_modified':before.last_modified},'after':{'etag':after.etag,'last_modified':after.last_modified}})
    elif action=='final-upload':upload('final/only-document.txt',b'The Solstice observatory telescope is named copper ibis.\n')
    elif action=='final-delete':
        c.delete_blob('final/only-document.txt');events.append({'action':'delete','name':'final/only-document.txt'})
    elif action=='formats':
        for ext in ['txt','md','markdown','json','csv','xml','yaml','yml','log','html','htm','rst','TXT']:
            upload(f'formats/sample.{ext}',f'The {ext} sample contains a format validation fact.\n'.encode())
        for name,payload in {'bom.txt':b'\xef\xbb\xbfBOM decoded without marker.','invalid.txt':b'Invalid byte replaced: \xff.','skip.pdf':b'%PDF-test','noextension':b'unsupported','folder/':b''}.items():upload('formats/'+name,payload)
    elif action=='race-upload':upload('race/document.txt',b'The Iris beacon code is bronze falcon.\n')
    else:raise ValueError(action)
    inventory=[{'name':b.name,'size':b.size,'etag':b.etag,'last_modified':b.last_modified} for b in c.list_blobs()]
result={'time':datetime.now(UTC).isoformat(),'action':action,'events':events,'inventory':inventory}
(ROOT/'evidence'/f'mutation-{action}.json').write_text(json.dumps(result,default=str,indent=2))
print(action, 'complete;',len(inventory),'blobs in container')
