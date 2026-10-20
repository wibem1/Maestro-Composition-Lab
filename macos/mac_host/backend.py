"""Platform-independent supervision of the bundled local service."""
from __future__ import annotations
import json,os,queue,re,signal,subprocess,threading,urllib.request
from pathlib import Path
from urllib.parse import urlsplit

class Backend:
 def __init__(self,python,engine,data):
  self.python=Path(python);self.engine=Path(engine);self.data=Path(data)
  self.process=None;self.url=None;self.token=None
  self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def start(self,timeout=20):
  if not self.python.is_file() or not self.engine.is_file():raise RuntimeError('Die App ist unvollständig. Bitte das gesamte Paket erneut entpacken.')
  self.data.mkdir(parents=True,exist_ok=True)
  env={**os.environ,'MAESTRO_DATA_DIR':str(self.data),'MAESTRO_PARENT_PID':str(os.getpid()),'MAESTRO_OWN_PROCESS_GROUP':'1','PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'}
  self.process=subprocess.Popen([str(self.python),'-B','-s','-E',str(self.engine),'--desktop'],cwd=str(self.engine.parent),env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',start_new_session=True)
  result=queue.Queue()
  def first_line():
   try:result.put(self.process.stdout.readline(4096))
   except (OSError,ValueError):result.put('')
  threading.Thread(target=first_line,daemon=True).start()
  try:
   line=result.get(timeout=timeout)
   if not line.startswith('MAESTRO_DESKTOP '):raise RuntimeError('Der lokale App-Dienst konnte nicht gestartet werden.')
   info=json.loads(line.removeprefix('MAESTRO_DESKTOP '));url=urlsplit(info['url'])
   if url.scheme!='http' or url.hostname!='127.0.0.1' or not url.port or url.path!='/' or url.query or url.fragment or url.username or not re.fullmatch(r'[A-Za-z0-9_-]{16,}',info['token']):raise RuntimeError('Ungültige Startbestätigung des App-Dienstes.')
   self.url=info['url'];self.token=info['token'];self.request('health',None)
   return info
  except queue.Empty:
   self.stop();raise RuntimeError('Der lokale App-Dienst startet nicht rechtzeitig.') from None
  except Exception:
   self.stop();raise
 def request(self,route,body):
  if not self.url:raise RuntimeError('App-Dienst nicht bereit.')
  data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
  req=urllib.request.Request(self.url+route.lstrip('/'),data=data,headers={'Content-Type':'application/json','X-Session':self.token})
  with self.opener.open(req,timeout=10) as response:return json.load(response)
 def stop(self):
  proc=self.process
  if proc is None:return
  try:
   if proc.poll() is None:
    try:self.request('shutdown',{})
    except Exception:pass
    try:proc.wait(timeout=4)
    except subprocess.TimeoutExpired:pass
   try:os.killpg(proc.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:proc.wait(timeout=2)
   except subprocess.TimeoutExpired:
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    proc.wait(timeout=2)
  finally:
   if proc.stdout:proc.stdout.close()
   self.process=None;self.url=None;self.token=None
