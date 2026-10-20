"""Entry point: no external interpreter or package installation is required."""
from pathlib import Path
import os,sys
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root));resources=root.parent
cert=resources/'runtime/lib/python3.13/site-packages/certifi/cacert.pem'
if cert.is_file():os.environ['SSL_CERT_FILE']=str(cert)
try:
 if '--self-test' in sys.argv:
  import json,platform
  from backend import Backend
  from native_core import data_folder
  import objc,AppKit,WebKit,Security,ssl
  with objc.autorelease_pool():
   data=data_folder();data.mkdir(parents=True,exist_ok=True)
   b=Backend(sys.executable,resources/'engine/maestro_analyse.py',data)
   try:
    b.start();info=b.request('desktop/info',{});info['architecture']=platform.machine();info['native_frameworks']='AppKit/WebKit/Security';info['ssl_ca_file']=cert.is_file()
    (data/'Desktop-Selbsttest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
   finally:b.stop()
 else:
  from app import main
  main(resources)
except Exception as error:
 import subprocess
 from native_core import data_folder
 data=data_folder();data.mkdir(parents=True,exist_ok=True)
 message=type(error).__name__+': '+str(error)
 (data/'Letzter-Startfehler.txt').write_text(message,encoding='utf-8')
 subprocess.run(['/usr/bin/osascript','-e','on run argv\ndisplay alert "Maestro Composition Lab" message (item 1 of argv)\nend run',message],check=False)
 sys.exit(1)
