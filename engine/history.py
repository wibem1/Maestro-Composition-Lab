"""Local result history. Existing JSON results are the source of truth."""
from pathlib import Path
import copy,datetime,json,threading,uuid
import composition as c

LABELS={'compose':'Komposition','analysis':'Analyse','continue':'Fortsetzung',
        'instruments':'Instrumente ergänzt','revise':'Überarbeitung'}
MAX_BYTES=32_000_000
_cache={}
_lock=threading.RLock()

def folder(api):
    import os
    return Path(os.environ.get('MAESTRO_DATA_DIR',str(api.ROOT)))/'Ergebnisse'

def text(value,limit=200):return str(value or '')[:limit]

def timestamp(seconds):
    return datetime.datetime.fromtimestamp(seconds,datetime.timezone.utc).isoformat()

def read_file(path):
    if path.stat().st_size>MAX_BYTES:raise c.ScoreError('Dieser Arbeitsstand ist zu groß zum Öffnen.')
    try:
        value=json.loads(path.read_text(encoding='utf-8-sig'))
    except (UnicodeError,ValueError) as error:
        raise c.ScoreError('Der gespeicherte Arbeitsstand ist beschädigt oder kein gültiges JSON.') from error
    if not isinstance(value,dict):raise c.ScoreError('Die Datei enthält keinen Arbeitsstand.')
    return value

def summary(path,stat):
    item={'id':path.name,'title':path.stem,'mode':'unknown','kind':'Arbeitsstand',
          'created_at':timestamp(stat.st_mtime),'updated_at':timestamp(stat.st_mtime),
          'provider':'','model':'','task':'','status':'Nicht lesbar'}
    try:
        data=read_file(path)
        mode=data.get('mode') or ('compose' if 'composition' in data or 'raw_response' in data else 'unknown')
        composition=data.get('composition') or {};source=data.get('source') or {}
        title=(composition.get('title') if isinstance(composition,dict) else '') or (source.get('title') if isinstance(source,dict) else '') or data.get('title') or data.get('task') or path.stem
        state='Prüfung fehlgeschlagen' if data.get('validation_error') else 'Angewendet' if data.get('applied') or data.get('inserted_into') else 'Analyse' if mode=='analysis' else 'Vorschlag'
        if (data.get('transfer') or {}).get('error'):state='Übertragung fehlgeschlagen'
        item.update(title=text(title,200),mode=mode,kind=LABELS.get(mode,'Arbeitsstand'),
                    created_at=data.get('created') or item['created_at'],provider=text(data.get('provider')),
                    model=text(data.get('model')),task=text(data.get('task'),1000),status=state)
    except (OSError,c.ScoreError,AttributeError,TypeError):pass
    return item

def listing(api,request):
    directory=folder(api);rows=[]
    with _lock:
        known=set()
        for path in directory.glob('*.json'):
            try:
                if path.is_symlink() or not path.is_file():continue
                stat=path.stat();key=str(path.resolve());known.add(key)
                signature=(stat.st_mtime_ns,stat.st_size)
                cached=_cache.get(key)
                if not cached or cached[0]!=signature:
                    cached=(signature,summary(path,stat));_cache[key]=cached
                rows.append((stat.st_mtime_ns,copy.deepcopy(cached[1])))
            except OSError:continue
        for key in list(_cache):
            if Path(key).parent==directory.resolve() and key not in known:_cache.pop(key,None)
    rows.sort(key=lambda x:(x[0],x[1]['id']),reverse=True)
    query=text(request.get('query'),1000).strip().casefold();mode=request.get('mode','all')
    if mode!='all' and mode not in LABELS:raise c.ScoreError('Unbekannter Verlaufsfilter.')
    items=[r for _,r in rows if (mode=='all' or r['mode']==mode) and
           (not query or query in ' '.join(str(r[k]) for k in ('title','task','provider','model','kind','status')).casefold())]
    offset=request.get('offset',0);limit=request.get('limit',50)
    if type(offset)!=int or offset<0 or type(limit)!=int or not 1<=limit<=200:raise c.ScoreError('Ungültige Verlaufsseite.')
    return {'items':items[offset:offset+limit],'total':len(items),'all_count':len(rows),
            'next_offset':offset+limit if offset+limit<len(items) else None}

def open_record(api,name):
    if not isinstance(name,str) or not name or Path(name).name!=name or '/' in name or '\\' in name or not name.lower().endswith('.json'):
        raise c.ScoreError('Ungültiger Verlaufseintrag.')
    path=folder(api)/name
    if path.is_symlink() or not path.is_file():raise c.ScoreError('Dieser Arbeitsstand ist nicht mehr vorhanden. Bitte den Verlauf aktualisieren.')
    value=read_file(path)
    if value.get('validation_error'):
        # Keep failed responses inspectable without attempting to apply them.
        record=copy.deepcopy(value);record['id']=uuid.uuid4().hex
        if value.get('mode')=='continue' and value.get('composition') is None:
            from workflows import load
            try:record=load(api,json.dumps(value,ensure_ascii=False),save=False)
            except (ValueError,TypeError,KeyError,IndexError):pass
        if record.get('mode') not in LABELS:record['mode']='compose'
    else:
        from workflows import load
        record=load(api,json.dumps(value,ensure_ascii=False),save=False)
    record['saved_path']=str(path)
    record['history_origin']={'file':name,'id':value.get('id')}
    return record
