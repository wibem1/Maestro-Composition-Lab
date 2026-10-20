"""macOS Keychain generic passwords. Keys never enter settings.json or argv."""
import contextlib,functools,sys
SERVICE='Maestro Composition Lab'

def native_pool(function):
 @functools.wraps(function)
 def call(*args,**kwargs):
  if sys.platform=='darwin':
   import objc
   pool=objc.autorelease_pool()
  else:pool=contextlib.nullcontext()
  with pool:return function(*args,**kwargs)
 return call

def frameworks():
 import Security
 from Foundation import NSData
 return Security,NSData

def query(security,provider):
 return {security.kSecClass:security.kSecClassGenericPassword,security.kSecAttrService:SERVICE,security.kSecAttrAccount:provider}

def status(value):return value[0] if isinstance(value,tuple) else value

@native_pool
def store(provider,key):
 s,data=frameworks();q=query(s,provider);value=data.dataWithBytes_length_(key.encode('utf-8'),len(key.encode('utf-8')))
 result=status(s.SecItemAdd({**q,s.kSecValueData:value},None))
 if result==s.errSecDuplicateItem:result=status(s.SecItemUpdate(q,{s.kSecValueData:value}))
 if result!=s.errSecSuccess:raise ValueError('Der macOS-Schlüsselbund konnte den API-Schlüssel nicht speichern (Status '+str(result)+').')
 return provider

@native_pool
def load(provider):
 s,_=frameworks();result=s.SecItemCopyMatching({**query(s,provider),s.kSecReturnData:True,s.kSecMatchLimit:s.kSecMatchLimitOne},None)
 code,value=result
 if code==s.errSecItemNotFound:return ''
 if code!=s.errSecSuccess:raise ValueError('Der macOS-Schlüsselbund konnte den API-Schlüssel nicht öffnen (Status '+str(code)+').')
 return bytes(value).decode('utf-8')

@native_pool
def delete(provider):
 s,_=frameworks();result=status(s.SecItemDelete(query(s,provider)))
 if result not in (s.errSecSuccess,s.errSecItemNotFound):raise ValueError('Der macOS-Schlüsselbund konnte den gespeicherten API-Schlüssel nicht entfernen (Status '+str(result)+').')
