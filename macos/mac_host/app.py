"""Native macOS window around the shared Composition Lab engine."""
from __future__ import annotations
import json,os,platform,sys,threading
from pathlib import Path
import objc
import AppKit as A
import Foundation as F
import WebKit as W
from PyObjCTools import AppHelper
from backend import Backend
from native_core import APP_NAME,VERSION,data_folder,own_page,bridge_message,open_json,diagnostic

PROTOCOLS=[objc.protocolNamed('WKScriptMessageHandler')]

class AppDelegate(F.NSObject,protocols=PROTOCOLS):
 @objc.python_method
 def configure(self,resources):
  self.resources=Path(resources);self.data=data_folder();self.data.mkdir(parents=True,exist_ok=True)
  self.backend=Backend(sys.executable,self.resources/'engine/maestro_analyse.py',self.data)
  self.ready=False;self.quitting=False;self.zoom=1.0;self.start_thread=None
  return self

 def applicationDidFinishLaunching_(self,notification):
  try:
   F.NSProcessInfo.processInfo().setProcessName_(APP_NAME)
   icon=self.resources/'AppIcon.icns'
   if icon.exists():A.NSApplication.sharedApplication().setApplicationIconImage_(A.NSImage.alloc().initWithContentsOfFile_(str(icon)))
   self.build_menu()
   style=A.NSWindowStyleMaskTitled|A.NSWindowStyleMaskClosable|A.NSWindowStyleMaskMiniaturizable|A.NSWindowStyleMaskResizable
   screen=A.NSScreen.mainScreen().visibleFrame().size
   size=(min(1180,max(760,screen.width-40)),min(850,max(580,screen.height-40)))
   self.window=A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(((0,0),size),style,A.NSBackingStoreBuffered,False)
   self.window.setTitle_(APP_NAME);self.window.setMinSize_((760,580));self.window.center()
   self.window.setFrameAutosaveName_('MaestroCompositionLab.MainWindow')
   F.NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(self, 'windowClosed:', A.NSWindowWillCloseNotification, self.window)
   config=W.WKWebViewConfiguration.alloc().init()
   config.setWebsiteDataStore_(W.WKWebsiteDataStore.nonPersistentDataStore())
   config.userContentController().addScriptMessageHandler_name_(self,'maestroNative')
   self.web=W.WKWebView.alloc().initWithFrame_configuration_(self.window.contentView().bounds(),config)
   self.web.setAutoresizingMask_(A.NSViewWidthSizable|A.NSViewHeightSizable)
   self.window.setContentView_(self.web)
   self.show_loading('Der lokale App-Dienst wird gestartet …')
   self.window.makeKeyAndOrderFront_(None);A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
   self.start_thread=threading.Thread(target=self.start_service,daemon=True);self.start_thread.start()
  except Exception as error:self.show_error(error)

 @objc.python_method
 def start_service(self):
  try:
   self.backend.start()
   AppHelper.callAfter(self.service_started)
  except Exception as error:AppHelper.callAfter(self.show_error,error)

 @objc.python_method
 def service_started(self):
  if not self.quitting:
   self.show_loading('Der App-Dienst läuft. Oberfläche wird geladen …')
   self.web.loadRequest_(F.NSURLRequest.requestWithURL_(F.NSURL.URLWithString_(self.backend.url)))
   self.ready=True

 @objc.python_method
 def show_loading(self,message):
  page='<html><head><meta charset="utf-8"></head><body style="font:17px -apple-system,BlinkMacSystemFont,sans-serif;background:#f1f4f4;color:#263b3d;padding:44px"><h2>Maestro Composition Lab</h2><p>'+message+'</p></body></html>'
  self.web.loadHTMLString_baseURL_(page,None)

 @objc.python_method
 def build_menu(self):
  bar=A.NSMenu.alloc().initWithTitle_('')
  def submenu(title):
   top=A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title,None,'');menu=A.NSMenu.alloc().initWithTitle_(title)
   bar.addItem_(top);top.setSubmenu_(menu);return menu
  def item(menu,title,selector,key=''):
   value=A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title,selector,key)
   if selector:value.setTarget_(self)
   menu.addItem_(value);return value
  app=submenu(APP_NAME);item(app,'Über '+APP_NAME,'about:');app.addItem_(A.NSMenuItem.separatorItem())
  item(app,APP_NAME+' ausblenden','hideApp:','h');app.addItem_(A.NSMenuItem.separatorItem());item(app,'Beenden','quit:','q')
  file=submenu('Datei');item(file,'Arbeitsstand öffnen …','openComposition:','o');item(file,'Ergebnisordner öffnen','openResults:')
  file.addItem_(A.NSMenuItem.separatorItem());item(file,'Fenster schließen','quit:','w')
  edit=submenu('Bearbeiten')
  for title,selector,key in [('Widerrufen','undo:','z'),('Ausschneiden','cut:','x'),('Kopieren','copy:','c'),('Einsetzen','paste:','v'),('Alles auswählen','selectAll:','a')]:
   value=item(edit,title,None,key);value.setAction_(selector);value.setTarget_(None)
  view=submenu('Ansicht');item(view,'Vergrößern','zoomIn:','+');item(view,'Verkleinern','zoomOut:','-');item(view,'Originalgröße','zoomReset:','0')
  help=submenu('Hilfe');item(help,'Diagnose sichern …','saveDiagnostics:')
  # Attach a fully populated menu: installing an empty bar lets AppKit insert
  # its own application item before ours, shifting the visible menus.
  self.menu_bar=bar
  A.NSApplication.sharedApplication().setMainMenu_(bar)
  A.NSApplication.sharedApplication().setHelpMenu_(help)

 def about_(self,sender):
  alert=A.NSAlert.alloc().init();alert.setMessageText_(APP_NAME+' '+VERSION)
  alert.setInformativeText_('19.10.2026\nKomponieren, analysieren, fortsetzen und überarbeiten mit Maestro.');alert.runModal()
 def hideApp_(self,sender):A.NSApplication.sharedApplication().hide_(sender)
 def quit_(self,sender):A.NSApplication.sharedApplication().terminate_(sender)
 def zoomIn_(self,sender):self.set_zoom(min(2.4,self.zoom+0.1))
 def zoomOut_(self,sender):self.set_zoom(max(0.6,self.zoom-0.1))
 def zoomReset_(self,sender):self.set_zoom(1.0)
 @objc.python_method
 def set_zoom(self,value):self.zoom=value;self.web.setMagnification_(value)

 @objc.typedSelector(b'c@:@c')
 def applicationShouldHandleReopen_hasVisibleWindows_(self,app,visible):
  if hasattr(self,'window'):self.window.makeKeyAndOrderFront_(None)
  return True
 @objc.typedSelector(b'v@:@')
 def windowClosed_(self,notification):
  A.NSApplication.sharedApplication().terminate_(self)
 def applicationShouldTerminate_(self,app):
  if self.quitting:return A.NSTerminateCancel
  self.quitting=True
  if not self.ready:self.finish_quit();return A.NSTerminateLater
  def checked(value,error):
   if error is None and bool(value):
    self.quitting=False;self.js_status('Bitte die laufende Anfrage erst abschließen lassen. Danach kannst du die App schließen.',True)
    app.replyToApplicationShouldTerminate_(False)
   else:self.finish_quit()
  self.web.evaluateJavaScript_completionHandler_("typeof busy !== 'undefined' && busy",checked)
  return A.NSTerminateLater
 # PyObjC otherwise infers a 32-bit unsigned return type from the enum.
 # Explicit 64-bit return type for termination reply.
 applicationShouldTerminate_ = objc.selector(applicationShouldTerminate_, signature=b'l@:@')
 @objc.python_method
 def finish_quit(self):
  def work():
   if self.start_thread and self.start_thread.is_alive():self.start_thread.join(timeout=35)
   self.backend.stop();AppHelper.callAfter(A.NSApplication.sharedApplication().replyToApplicationShouldTerminate_,True)
  threading.Thread(target=work,daemon=True).start()

 def userContentController_didReceiveScriptMessage_(self,controller,message):
  try:
   frame=message.frameInfo()
   if not frame.isMainFrame() or not own_page(frame.request().URL().absoluteString(),self.backend.url):return
   body=bridge_message(dict(message.body()))
   if body['type']=='save-json':self.save_json(body['name'],body['text'])
   elif body['type']=='copy':
    board=A.NSPasteboard.generalPasteboard();board.clearContents();board.setString_forType_(body['text'],A.NSPasteboardTypeString)
  except Exception as error:self.show_error(error)

 @objc.python_method
 def when_idle(self,callback):
  if not self.ready:return
  def checked(value,error):
   if error is not None:return
   if value:self.js_status('Bitte die laufende Anfrage erst abschließen lassen.',True)
   else:callback()
  self.web.evaluateJavaScript_completionHandler_("typeof busy !== 'undefined' && busy",checked)
 def openComposition_(self,sender):self.when_idle(self.open_panel)
 @objc.python_method
 def open_panel(self):
  panel=A.NSOpenPanel.openPanel();panel.setAllowedFileTypes_(['json']);panel.setAllowsMultipleSelection_(False)
  if panel.runModal()!=A.NSModalResponseOK:return
  try:self.send_message(open_json(panel.URL().path()))
  except Exception as error:self.show_error(error)
 @objc.python_method
 def send_message(self,value):
  self.web.evaluateJavaScript_completionHandler_('window.maestroNativeMessage('+json.dumps(value,ensure_ascii=True)+')',None)
 def openResults_(self,sender):
  folder=self.data/'Ergebnisse';folder.mkdir(parents=True,exist_ok=True)
  A.NSWorkspace.sharedWorkspace().openURL_(F.NSURL.fileURLWithPath_(str(folder)))
 def saveDiagnostics_(self,sender):
  def work():
   try:service=self.backend.request('desktop/info',{}) if self.backend.url else 'Nicht bereit'
   except Exception:service='Nicht bereit'
   value=diagnostic(service);AppHelper.callAfter(self.save_json,'Maestro-App-Diagnose.json',json.dumps(value,ensure_ascii=False,indent=2))
  threading.Thread(target=work,daemon=True).start()
 @objc.python_method
 def save_json(self,name,text):
  panel=A.NSSavePanel.savePanel();panel.setAllowedFileTypes_(['json']);panel.setNameFieldStringValue_(name)
  if panel.runModal()!=A.NSModalResponseOK:return
  try:Path(panel.URL().path()).write_text(text,encoding='utf-8')
  except Exception as error:self.show_error(error)
 @objc.python_method
 def js_status(self,message,bad=False):
  if self.ready:self.web.evaluateJavaScript_completionHandler_('status('+json.dumps(message)+','+('true' if bad else 'false')+')',None)
 @objc.python_method
 def show_error(self,error):
  if self.quitting:return
  message=str(error)
  try:(self.data/'Letzter-Startfehler.txt').write_text(type(error).__name__+'\n'+message,encoding='utf-8')
  except OSError:pass
  
  if hasattr(self,'web'):
   try:self.show_loading('Startfehler: '+message.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))
   except Exception:pass
  alert=A.NSAlert.alloc().init();alert.setMessageText_(APP_NAME);alert.setInformativeText_(message);alert.runModal()


def main(resources):
 app=A.NSApplication.sharedApplication();app.setActivationPolicy_(A.NSApplicationActivationPolicyRegular)
 delegate=AppDelegate.alloc().init().configure(resources);app.setDelegate_(delegate)
 # Keep a strong Python reference: NSApplication's delegate is not retained.
 globals()['_delegate']=delegate
 AppHelper.runEventLoop()
