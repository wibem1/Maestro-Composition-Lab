"""Native-host rules that can also be tested without AppKit."""
import json,platform,sys
from pathlib import Path
from urllib.parse import urlsplit
VERSION='3.0.0'
APP_NAME='Maestro Composition Lab'

def data_folder(home=None):return Path(home or Path.home())/'Library/Application Support/Maestro-Composition-Lab'

def own_page(url,base):
 try:
  a=urlsplit(str(url));b=urlsplit(str(base))
  return bool(base) and a.scheme==b.scheme=='http' and a.hostname==b.hostname=='127.0.0.1' and a.port==b.port and a.username is None and a.password is None
 except (ValueError,TypeError):return False

def bridge_message(body):
 if not isinstance(body,dict):raise ValueError('Ungültige App-Nachricht.')
 if body.get('type') not in ('save-json','copy'):raise ValueError('Unbekannte App-Nachricht.')
 text=body.get('text')
 if not isinstance(text,str) or len(text.encode('utf-8'))>32_000_000:raise ValueError('Die Datei oder der Text ist zu groß.')
 if body['type']=='save-json':
  json.loads(text)
  name=Path(str(body.get('name','Arbeitsstand.json')).replace('\\','/')).name
  if not name.lower().endswith('.json'):name='Arbeitsstand.json'
  return {'type':'save-json','name':name[:150],'text':text}
 return {'type':'copy','text':text}

def open_json(path):
 path=Path(path)
 if path.stat().st_size>32_000_000:raise ValueError('Die Datei ist zu groß.')
 text=path.read_text(encoding='utf-8-sig');json.loads(text)
 return {'type':'open-composition','text':text}

def diagnostic(service,webview='WKWebView'):
 return {'app':APP_NAME,'version':VERSION,'macos':platform.mac_ver()[0],
         'architecture':platform.machine(),'python':sys.version.split()[0],
         'webview':webview,'service':service}
