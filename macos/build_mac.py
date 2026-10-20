"""Reproducible Mac .app assembly using pinned, hash-verified dependencies.

The runtimes and PyObjC extensions are already compiled by their upstreams.
This builder runs on Linux or macOS. It does not pretend to execute AppKit on Linux.
"""
from __future__ import annotations
import hashlib,json,os,plistlib,shutil,stat,struct,tarfile,tempfile,urllib.request,zipfile
from pathlib import Path
SOURCE=Path(__file__).resolve().parent;ROOT=SOURCE.parent
LOCK=json.loads((SOURCE/'dependencies.json').read_text())
CACHE=ROOT/'build/dependencies'
APP='Maestro Composition Lab.app'
VERSION='3.0.0'

def source_dependency(item):
 CACHE.mkdir(parents=True,exist_ok=True);path=CACHE/item['name']
 if not path.exists():
  with urllib.request.urlopen(item['url'],timeout=180) as response:path.write_bytes(response.read())
 if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Dependency hash mismatch: '+item['name'])
 return path

def icon(path):
 # Repackage the existing PNG icon sizes as ICNS without modifying their pixels.
 data=(SOURCE/'AppIcon.ico').read_bytes();count=struct.unpack_from('<H',data,4)[0];parts=[]
 tags={16:b'icp4',32:b'icp5',64:b'icp6',128:b'ic07',256:b'ic08'}
 for i in range(count):
  width,height,_,_,_,_,length,offset=struct.unpack_from('<BBBBHHII',data,6+16*i);width=width or 256;height=height or 256
  payload=data[offset:offset+length]
  if width in tags and width==height and payload.startswith(b'\x89PNG\r\n\x1a\n'):parts.append(tags[width]+struct.pack('>I',length+8)+payload)
 raw=b''.join(parts);path.write_bytes(b'icns'+struct.pack('>I',len(raw)+8)+raw)

def zip_tree(directory,archive):
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for path in sorted(directory.rglob('*')):
   name=path.relative_to(directory.parent).as_posix();info=zipfile.ZipInfo(name);info.create_system=3
   if path.is_symlink():
    info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,os.readlink(path))
   elif path.is_file():
    info.external_attr=path.stat().st_mode<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,path.read_bytes())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for path in directory.rglob('*'):
   if path.is_symlink():assert z.read(path.relative_to(directory.parent).as_posix()).decode()==os.readlink(path)
   elif path.is_file():assert z.read(path.relative_to(directory.parent).as_posix())==path.read_bytes()

def build(arch,label):
 final_destination=ROOT/'dist'/f'Maestro-Composition-Lab-{VERSION}-Mac-{label}'
 stage=Path(tempfile.mkdtemp(prefix='maestro-mac-stage-'))
 destination=stage/final_destination.name
 contents=destination/APP/'Contents';resources=contents/'Resources';macos=contents/'MacOS'
 resources.mkdir(parents=True);macos.mkdir()
 runtime=next(item for item in LOCK['dependencies'] if item['kind']=='runtime' and item['arch']==arch)
 expanded=stage/'extracted'
 asset=source_dependency(runtime)
 expanded.mkdir(parents=True,exist_ok=True)
 with tarfile.open(asset) as t:t.extractall(expanded,filter='data')
 py=expanded/'python';site=py/'lib/python3.13/site-packages'
 for wheel in LOCK['dependencies']:
  if wheel['kind']=='wheel':
   with zipfile.ZipFile(source_dependency(wheel)) as z:z.extractall(site)
 shutil.copytree(py,resources/'runtime',symlinks=True,dirs_exist_ok=True)
 shutil.copytree(ROOT/'engine',resources/'engine',ignore=shutil.ignore_patterns('__pycache__','test_*.py','selftest.py','ui_selftest.js'))
 shutil.copytree(SOURCE/'mac_host',resources/'mac_host',ignore=shutil.ignore_patterns('__pycache__'))
 icon(resources/'AppIcon.icns')
 executable=macos/'maestro-lab'
 executable.write_text('''#!/bin/sh
set -eu
MAESTRO_RESOURCES="$(CDPATH= cd -- "$(dirname -- "$0")/../Resources" && pwd)"
exec "$MAESTRO_RESOURCES/runtime/bin/python3.13" -I -B "$MAESTRO_RESOURCES/mac_host/bootstrap.py" "$@"
''');executable.chmod(0o755)
 info={'CFBundleName':'Maestro Composition Lab','CFBundleDisplayName':'Maestro Composition Lab','CFBundleIdentifier':'net.klangwerke.maestro-composition-lab','CFBundleExecutable':'maestro-lab','CFBundlePackageType':'APPL','CFBundleShortVersionString':VERSION,'CFBundleVersion':VERSION,'CFBundleIconFile':'AppIcon','LSMinimumSystemVersion':'13.0','NSHighResolutionCapable':True,'NSPrincipalClass':'NSApplication','NSAppTransportSecurity':{'NSAllowsLocalNetworking':True},'LSArchitecturePriority':['arm64' if arch=='aarch64' else 'x86_64']}
 with (contents/'Info.plist').open('wb') as out:plistlib.dump(info,out)
 (contents/'PkgInfo').write_bytes(b'APPL????')
 for name in ('LIESMICH.txt','TESTSTAND.txt','ARCHITEKTUR.md','DRITTANBIETER.txt'):
  shutil.copy2(ROOT/name,destination/name)
 shutil.copytree(SOURCE,destination/'Quellcode',ignore=shutil.ignore_patterns('__pycache__'))
 helper=destination/'Mac-Selbsttest.command';helper.write_text('''#!/bin/sh
MAESTRO_PACKAGE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
MAESTRO_APP="$MAESTRO_PACKAGE/Maestro Composition Lab.app"
if [ ! -d "$MAESTRO_APP" ]; then MAESTRO_APP="/Applications/Maestro Composition Lab.app"; fi
if [ ! -d "$MAESTRO_APP" ]; then MAESTRO_APP="$HOME/Applications/Maestro Composition Lab.app"; fi
"$MAESTRO_APP/Contents/MacOS/maestro-lab" --self-test
MAESTRO_RESULT=$?
if [ "$MAESTRO_RESULT" -eq 0 ]; then
  echo "Selbsttest bestanden. Bericht: $HOME/Library/Application Support/Maestro-Composition-Lab/Desktop-Selbsttest.json"
else
  echo "Selbsttest fehlgeschlagen. Bericht: $HOME/Library/Application Support/Maestro-Composition-Lab/Letzter-Startfehler.txt"
fi
printf 'Zum Schliessen Enter druecken. '
read MAESTRO_UNUSED
exit "$MAESTRO_RESULT"
''');helper.chmod(0o755)
 for path in destination.rglob('*'):
  if path.is_symlink():
   assert path.resolve().is_relative_to(destination.resolve()),path
  elif path.is_file():
   if path.suffix in ('.so','.dylib') or path==resources/'runtime/bin/python3.13':path.chmod(0o755)
 checks=[]
 for path in sorted(destination.rglob('*')):
  if path.is_file() and not path.is_symlink():checks.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.relative_to(destination).as_posix())
 (destination/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n')
 archive=ROOT/f'Maestro-Composition-Lab-{VERSION}-Mac-{label}.zip'
 built_archive=stage/archive.name;zip_tree(destination,built_archive)
 shutil.copy2(built_archive,archive)
 print(label,archive.stat().st_size,archive,flush=True)
 return destination,archive

if __name__=='__main__':
 for arch,label in (('aarch64','AppleSilicon'),('x86_64','Intel')):build(arch,label)
