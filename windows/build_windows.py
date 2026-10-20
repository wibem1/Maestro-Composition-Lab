"""Assemble a relocatable x64 Windows app from a native build and CPython."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='3.0.1'
def main():
 if sys.platform!='win32':raise RuntimeError('Native Windows build required')
 package=ROOT/'dist'/f'Maestro-Composition-Lab-{VERSION}-Windows'
 if package.exists():shutil.rmtree(package)
 package.mkdir(parents=True)
 subprocess.run(['dotnet','build',str(ROOT/'windows/desktop/MaestroDesktop.csproj'),'-c','Release','-o',str(package)],check=True)
 runtime=package/'runtime';runtime.mkdir();base=Path(sys.base_prefix)
 for pattern in ('python*.exe','*.dll','LICENSE.txt'):
  for p in base.glob(pattern):shutil.copy2(p,runtime/p.name)
 for name in ('Lib','DLLs'):
  shutil.copytree(base/name,runtime/name,ignore=shutil.ignore_patterns('site-packages','__pycache__','test','tests','tkinter','idlelib','turtledemo','ensurepip'))
 shutil.copytree(ROOT/'engine',package/'engine',ignore=shutil.ignore_patterns('__pycache__','test_*.py','selftest.py','ui_selftest.js','index.html'))
 for name in ('LIESMICH.txt','TESTSTAND.txt','ARCHITEKTUR.md','DRITTANBIETER.txt'):shutil.copy2(ROOT/name,package/name)
 subprocess.run([str(runtime/'python.exe'),'-I','-c','import ssl,ctypes,json; print(ssl.OPENSSL_VERSION)'],check=True)
 completed=subprocess.run([str(package/'Maestro Composition Lab.exe'),'--self-test'],timeout=60)
 if completed.returncode:raise RuntimeError('Bundled Windows host self-test failed')
 (package/'BUILD.json').write_text(json.dumps({'version':VERSION,'python':sys.version,'commit':os.environ.get('GITHUB_SHA'),'native_host_selftest':'PASS'},indent=2))
 sums=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(package).as_posix() for p in sorted(package.rglob('*')) if p.is_file()]
 (package/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n')
 shutil.make_archive(str(ROOT/package.name),'zip',package.parent,package.name)
if __name__=='__main__':main()
