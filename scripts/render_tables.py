import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tables'
OUT.mkdir(exist_ok=True)

def read(name):
    return json.loads((ROOT / 'evidence' / name).read_text())

def rows(step, when):
    snapshot = read(f'{step}-{when}-sql.json')
    return {r['title']: r for db, tables in snapshot.items()
            if db.startswith('dlt_database_') and not db.endswith('_staging')
            for table, records in tables.items() if table == 'azure_blob_documents'
            for r in records}

def font(size, bold=False):
    name = 'Arial Bold.ttf' if bold else 'Arial Unicode.ttf'
    return ImageFont.truetype('/System/Library/Fonts/Supplemental/' + name, size)

def draw_table(filename, items):
    image = Image.new('RGB', (1800, 64 + len(items) * 94), '#f7f9fc')
    draw = ImageDraw.Draw(image)
    cols = [26, 410, 535, 810, 975]
    for x, label in zip(cols, ['Blob name', 'Bytes', 'Observed action', 'Read bytes', 'Content preview / reason']):
        draw.text((x, 17), label, font=font(22, True), fill='#172b45')
    colors = {'Added': '#177245', 'Updated': '#0078d4', 'Removed': '#a33b2b',
              'Skipped': '#6c7684', 'Excluded': '#6c7684', 'Unchanged': '#596c82',
              'Not processed': '#a96c00'}
    for index, (name, size, action, downloaded, preview, reason) in enumerate(items):
        y = 60 + index * 94
        draw.rectangle((16, y, 1784, y + 89), fill='white')
        draw.line((16, y + 90, 1784, y + 90), fill='#dce4ee')
        for x, value in zip(cols[:4], [name, str(size), action, str(downloaded)]):
            draw.text((x, y + 13), value, font=font(22, x == cols[2]),
                      fill=colors.get(action, '#172b45') if x == cols[2] else '#172b45')
        for line_index, line in enumerate(textwrap.wrap(preview, width=64)[:2]):
            draw.text((cols[4], y + 8 + line_index * 25), line, font=font(21), fill='#34495e')
        draw.text((cols[4], y + 63), reason, font=font(18), fill='#61748c')
    image.save(OUT / filename)

for file in sorted((ROOT / 'evidence').glob('*-result.json')):
    step = file.name.removesuffix('-result.json')
    result = read(file.name)
    before, after = rows(step, 'before'), rows(step, 'after')
    inventory = {b['name']: b for b in result['azure_inventory']
                 if b['name'].startswith(result['prefix']) or b['name'] == 'outside-prefix.txt'}
    downloads = {b['name']: b for b in result['downloads']}
    items = []
    for name in sorted(set(inventory) | set(before) | set(after)):
        blob, old, row = inventory.get(name), before.get(name), after.get(name)
        size = blob['size'] if blob else len((old or row)['content'].encode())
        if not name.startswith(result['prefix']):
            action, reason = 'Excluded', 'outside selected prefix'
        elif name.endswith('/') and size == 0:
            action, reason = 'Skipped', 'directory placeholder'
        elif result['status'] != 'completed':
            action, reason = 'Not processed', 'max_objects guard aborted extraction'
        elif row and name in downloads:
            action, reason = ('Updated' if old else 'Added'), 'conditional content download'
        elif row:
            action, reason = 'Unchanged', 'no content download'
        elif old:
            action, reason = 'Removed', ('now oversized' if blob and size > 1024 else 'confirmed BlobNotFound')
        else:
            action, reason = 'Skipped', ('above 1024-byte limit' if size > 1024 else 'unsupported text type')
        preview = (row or old or {}).get('content', '').strip()
        preview = preview or ('[empty content]' if row else '—')
        preview = preview.replace('\u2615', r'\u2615')
        if old and not row:
            preview = 'Last known: ' + preview
        items.append((name, size, action, downloads.get(name, {}).get('bytes', 0), preview, reason))
    draw_table(step + '.png', items)

extra = read('10-extra-live.json')['formats']
downloads = {e['name']: e for e in extra['events'] if e['op'] == 'download'}
items = []
for uri, text in sorted(extra['after']['rows'].items()):
    name = 'formats/' + uri.split('/formats/')[-1]
    size = downloads[name]['bytes']
    items.append((name, size, 'Added', size, text.strip(), 'downloaded and staged'))
draw_table('10-extra-live.png', items)
print(f'Rendered {len(list(OUT.glob("*.png")))} tables from saved evidence.')
