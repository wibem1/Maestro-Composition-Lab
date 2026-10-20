"""Local preferences; opt-in Windows DPAPI storage, never plaintext keys."""
import base64
import ctypes
import json
import os
import pathlib
import threading
import sys

PROVIDERS=('Google','OpenAI','Anthropic','OpenRouter')
LOCK=threading.Lock()

def settings_path():
    if os.environ.get('MAESTRO_DATA_DIR'):return pathlib.Path(os.environ['MAESTRO_DATA_DIR'])/'settings.json'
    if sys.platform=='darwin':return pathlib.Path.home()/'Library/Application Support/Maestro-Composition-Lab/settings.json'
    return pathlib.Path(os.environ.get('LOCALAPPDATA',str(pathlib.Path.home()/'.config')))/'Maestro-Composition-Lab'/'settings.json'

def crypt(data, decrypt=False):
    if os.name!='nt':raise ValueError('Geschütztes Speichern des Schlüssels ist nur unter Windows verfügbar.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buf=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    dll=ctypes.WinDLL('crypt32',use_last_error=True)
    if decrypt:
        fn=dll.CryptUnprotectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:
        fn=dll.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(source),'Maestro Composition Lab',None,None,None,1,ctypes.byref(target))
    fn.restype=wintypes.BOOL
    if not ok:raise ValueError('Windows konnte den API-Schlüssel nicht schützen bzw. öffnen.')
    try:return ctypes.string_at(target.data,target.size)
    finally:
        free=ctypes.WinDLL('kernel32').LocalFree
        free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
        free(target.data)

def _read():
    try:
        value=json.loads(settings_path().read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}

def load():
    with LOCK:data=_read()
    warnings=[]
    for provider,profile in data.get('profiles',{}).items():
        encrypted=profile.pop('protected_key',None)
        profile['key']='';profile['remember']=False
        if sys.platform=='darwin' and profile.get('keychain_account')==provider:
            try:
                import mac_keys
                profile['key']=mac_keys.load(provider);profile['remember']=bool(profile['key'])
            except (ValueError,OSError,UnicodeError):warnings.append('Gespeicherten API-Schlüssel bitte erneut eingeben.')
        elif encrypted:
            try:profile['key']=crypt(base64.b64decode(encrypted),True).decode('utf-8');profile['remember']=True
            except (ValueError,OSError,UnicodeError):warnings.append('Gespeicherten API-Schlüssel bitte erneut eingeben.')
    return {**data,'can_protect':os.name=='nt' or sys.platform=='darwin','warnings':warnings}

def save(data):
    provider=data.get('provider')
    if provider not in PROVIDERS:raise ValueError('Unbekannter Anbieter.')
    profile={'model':str(data.get('model',''))[:250]}
    if sys.platform=='darwin':
        import mac_keys
        if data.get('remember') and data.get('key'):profile['keychain_account']=mac_keys.store(provider,str(data['key']))
        else:mac_keys.delete(provider)
    elif data.get('remember') and data.get('key'):
        profile['protected_key']=base64.b64encode(crypt(str(data['key']).encode('utf-8'))).decode('ascii')
    with LOCK:
        current=_read();profiles=current.get('profiles',{});profiles[provider]=profile
        current={'provider':provider,'profiles':profiles,'mode':data.get('mode') if data.get('mode') in ('compose','analysis','continue','instruments','revise') else 'compose',
                 'path':str(data.get('path',''))[:2000], 'limit':int(data.get('limit',8192)),
                 'composeLimit':int(data.get('composeLimit',32768))}
        workspace=data.get('workspace',{})
        if isinstance(workspace,dict):
            current['workspace']={'reviseKind':'replace' if workspace.get('reviseKind')=='replace' else 'patch','tasks':{k:str(v)[:20000] for k,v in workspace.get('tasks',{}).items() if k in ('compose','analysis','continue','instruments','revise')},'bars':int(workspace.get('bars',16)),'barCounts':{k:int(v) for k,v in workspace.get('barCounts',{}).items() if k in ('compose','continue')},'ensembles':{}}
            current['workspace']['transitionEnabled']=workspace.get('transitionEnabled') is True
            tail=workspace.get('transitionBars',2)
            current['workspace']['transitionBars']=tail if type(tail)==int and tail in (2,3,4) else 2
            for mode in ('compose','instruments'):
                rows=workspace.get('ensembles',{}).get(mode,[])
                if isinstance(rows,list):current['workspace']['ensembles'][mode]=[{'name':str(st.get('name',''))[:120],'clef':str(st.get('clef','treble')),'program':int(st.get('program',0))} for st in rows if isinstance(st,dict)]
        path=settings_path();path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
        try:temp.chmod(0o600)
        except OSError:pass
        os.replace(temp,path)
    return {'ok':True}
