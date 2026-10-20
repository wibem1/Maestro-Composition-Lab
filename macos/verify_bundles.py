"""Verify native targets and complete relocatable bundle layout in the ZIP."""
from pathlib import Path,PurePosixPath
import os,plistlib,posixpath,stat,struct,subprocess,zipfile
ROOT=Path(__file__).resolve().parent.parent

def architectures(data):
 if data[:4] in (b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe'):return {struct.unpack_from('<I',data,4)[0]}
 if data[:4]==b'\xca\xfe\xba\xbe':return {struct.unpack_from('>I',data,8+20*i)[0] for i in range(struct.unpack_from('>I',data,4)[0])}
 raise AssertionError('Not a Mach-O binary: '+repr(data[:4]))

def verify(label,cpu):
 archive=ROOT/f'Maestro-Composition-Lab-2.6.0-Mac-{label}.zip'
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  prefix=f'Maestro-Composition-Lab-2.6.0-Mac-{label}/'
  app=prefix+'Maestro Composition Lab.app/Contents/'
  info=plistlib.loads(z.read(app+'Info.plist'))
  assert info['CFBundleShortVersionString']=='2.6.0' and info['LSMinimumSystemVersion']=='13.0'
  launcher=app+'MacOS/'+info['CFBundleExecutable'];assert (z.getinfo(launcher).external_attr>>16)&0o111
  subprocess.run(['/bin/sh','-n'],input=z.read(launcher),check=True)
  runtime=app+'Resources/runtime/'
  assert cpu in architectures(z.read(runtime+'bin/python3.13'))
  count=1
  for item in z.infolist():
   mode=item.external_attr>>16
   if stat.S_ISLNK(mode):
    target=z.read(item.filename).decode();assert not target.startswith('/')
    resolved=posixpath.normpath(posixpath.join(posixpath.dirname(item.filename),target))
    assert resolved.startswith(runtime),item.filename
    assert resolved in z.namelist(),resolved
   elif item.filename.startswith(runtime) and item.filename.endswith(('.so','.dylib')):
    assert cpu in architectures(z.read(item)),item.filename;count+=1
  for name in ('certifi/cacert.pem','objc/__init__.py','AppKit/__init__.py','WebKit/__init__.py','Security/__init__.py'):
   assert runtime+'lib/python3.13/site-packages/'+name in z.namelist(),name
  assert app+'Resources/engine/transition.py' in z.namelist()
  assert app+'Resources/mac_host/bootstrap.py' in z.namelist()
  subprocess.run(['/bin/sh','-n'],input=z.read(prefix+'Mac-Selbsttest.command'),check=True)
  assert len(z.read(app+'Resources/AppIcon.icns'))>1000
  print(label,':',count,'native Mach-O binaries match; runtime, bridge, CA bundle, manifest, scripts, modes and links verified')

if __name__=='__main__':
 for label,cpu in (('AppleSilicon',0x0100000c),('Intel',0x01000007)):verify(label,cpu)
