using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace MaestroDesktop {
 static class Program {
  public const string Version="3.0.1";
  public static readonly string Root=AppDomain.CurrentDomain.BaseDirectory;
  public static readonly string Data=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Maestro-Composition-Lab");
  public static readonly JavaScriptSerializer Json=new JavaScriptSerializer { MaxJsonLength=32000000 };
  [DllImport("user32.dll")]static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")]static extern bool ShowWindow(IntPtr hWnd,int nCmdShow);
  [STAThread] static int Main(string[] args) {
   Directory.CreateDirectory(Data);
   if(args.Contains("--self-test"))return SelfTest();
   using(var mutex=new Mutex(true,"Local\\MaestroCompositionLab.Desktop",out bool first)) {
    if(!first) {
     foreach(var p in Process.GetProcessesByName(Process.GetCurrentProcess().ProcessName)) {
      if(p.Id!=Process.GetCurrentProcess().Id&&p.MainWindowHandle!=IntPtr.Zero){ShowWindow(p.MainWindowHandle,9);SetForegroundWindow(p.MainWindowHandle);break;}
     }
     return 0;
    }
    Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
    Application.ThreadException+=(s,e)=>ReportError(e.Exception);
    try { Application.Run(new MainWindow());return 0; } catch(Exception e) { ReportError(e);return 1; }
   }
  }
  public static void ReportError(Exception e) {
   try { File.WriteAllText(Path.Combine(Data,"Letzter-Startfehler.txt"),DateTime.Now.ToString("s")+"\n"+e.GetType().Name+"\n"+e.Message,Encoding.UTF8); }catch{}
   MessageBox.Show(e.Message+"\n\nDiagnose: "+Data,"Maestro Composition Lab",MessageBoxButtons.OK,MessageBoxIcon.Error);
  }
  static int SelfTest() {
   try {
    using(var session=new BackendSession(Data)) {
     session.StartAsync(Path.Combine(Root,"runtime","python.exe"),Path.Combine(Root,"engine","maestro_analyse.py")).GetAwaiter().GetResult();
     string result=session.PostAsync("desktop/info","{}").GetAwaiter().GetResult();
     File.WriteAllText(Path.Combine(Data,"Desktop-Selbsttest.json"),result,Encoding.UTF8);
    }
    return 0;
   }catch(Exception e){File.WriteAllText(Path.Combine(Data,"Desktop-Selbsttest-Fehler.txt"),e.ToString(),Encoding.UTF8);return 1;}
  }
 }
 sealed class WindowSettings {
  public int X {get;set;} public int Y {get;set;} public int Width {get;set;}=1180;public int Height {get;set;}=850;
  public bool Maximized {get;set;}
 }
 sealed class MainWindow : Form {
  readonly WebView2 view=new WebView2 { Dock=DockStyle.Fill,DefaultBackgroundColor=Color.FromArgb(237,241,240) };
  readonly Label loading=new Label { Dock=DockStyle.Fill,Text="Maestro Composition Lab wird gestartet …",TextAlign=ContentAlignment.MiddleCenter,Font=new Font("Segoe UI",13) };
  readonly BackendSession backend=new BackendSession(Program.Data);
  readonly OwnedProcessJob job=new OwnedProcessJob();
  bool ready,closing,closed,allowClose;
  readonly string windowFile=Path.Combine(Program.Data,"Fenster.json");
  public MainWindow() {
   Text="Maestro Composition Lab";MinimumSize=new Size(760,580);Size=new Size(1180,850);StartPosition=FormStartPosition.CenterScreen;
   Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);
   Controls.Add(view);Controls.Add(loading);Controls.Add(BuildMenu());MainMenuStrip=Controls.OfType<MenuStrip>().First();
   backend.OnStarted=job.Own;
   RestoreBoundsFromFile();Shown+=async(s,e)=>await StartAsync();FormClosing+=ClosingAsync;
   FormClosed+=(s,e)=>{closed=true;backend.Dispose();job.Dispose();};
  }
  MenuStrip BuildMenu() {
   var menu=new MenuStrip();var file=new ToolStripMenuItem("Datei");
   file.DropDownItems.Add("Arbeitsstand öffnen …",null,async(s,e)=>await OpenComposition());
   file.DropDownItems.Add("Ergebnisordner öffnen",null,(s,e)=>{var folder=Path.Combine(Program.Data,"Ergebnisse");Directory.CreateDirectory(folder);Process.Start(new ProcessStartInfo(folder){UseShellExecute=true});});
   file.DropDownItems.Add("Verknüpfung im Startmenü erstellen",null,(s,e)=>CreateShortcut());
   file.DropDownItems.Add(new ToolStripSeparator());file.DropDownItems.Add("Beenden",null,(s,e)=>Close());
   var display=new ToolStripMenuItem("Ansicht");
   display.DropDownItems.Add("Vergrößern",null,(s,e)=>view.ZoomFactor=Math.Min(2,view.ZoomFactor+0.1));
   display.DropDownItems.Add("Verkleinern",null,(s,e)=>view.ZoomFactor=Math.Max(0.6,view.ZoomFactor-0.1));
   display.DropDownItems.Add("Originalgröße",null,(s,e)=>view.ZoomFactor=1);
   var help=new ToolStripMenuItem("Hilfe");help.DropDownItems.Add("Diagnose speichern …",null,async(s,e)=>await SaveDiagnostics());
   help.DropDownItems.Add("Über Maestro Composition Lab",null,(s,e)=>MessageBox.Show("Maestro Composition Lab "+Program.Version+"\n20.10.2026\nKomposition, Analyse und direkte Übergabe an Maestro.\nEigenständige Begleit-App; kein Bestandteil von Maestro.","Über",MessageBoxButtons.OK,MessageBoxIcon.Information));
   menu.Items.AddRange(new ToolStripItem[]{file,display,help});return menu;
  }
  async Task StartAsync() {
   try {
    await backend.StartAsync(Path.Combine(Program.Root,"runtime","python.exe"),Path.Combine(Program.Root,"engine","maestro_analyse.py"));
    if(closed||closing)return;
    var environment=await CoreWebView2Environment.CreateAsync(null,Path.Combine(Program.Data,"WebView"));
    if(closed||closing)return;
    await view.EnsureCoreWebView2Async(environment);
    view.CoreWebView2.Settings.AreDevToolsEnabled=false;view.CoreWebView2.Settings.IsStatusBarEnabled=false;
    view.CoreWebView2.Settings.AreDefaultContextMenusEnabled=false;
    view.CoreWebView2.NewWindowRequested+=(s,e)=>e.Handled=true;
    view.CoreWebView2.NavigationStarting+=(s,e)=>{if(!IsOwnPage(e.Uri))e.Cancel=true;};
    view.CoreWebView2.WebMessageReceived+=(s,e)=>{if(IsOwnPage(e.Source)&&e.TryGetWebMessageAsString()=="quit")Close();};
    view.CoreWebView2.PermissionRequested+=(s,e)=>{if(IsOwnPage(e.Uri)&&e.PermissionKind==CoreWebView2PermissionKind.ClipboardRead)e.State=CoreWebView2PermissionState.Allow;};
    view.CoreWebView2.DownloadStarting+=(s,e)=>{
     using(var dialog=new SaveFileDialog { FileName=Path.GetFileName(e.ResultFilePath),Filter="Alle Dateien|*.*",OverwritePrompt=true }) {
      if(dialog.ShowDialog(this)==DialogResult.OK){e.ResultFilePath=dialog.FileName;e.Handled=true;}else e.Cancel=true;
     }
    };
    view.NavigationCompleted+=(s,e)=>{
     if(e.IsSuccess){ready=true;loading.Visible=false;}
     else {loading.Text="Die Oberfläche konnte nicht geladen werden. Bitte die App neu starten.";}
    };
    view.Source=backend.Address;
   }catch(WebView2RuntimeNotFoundException){
    loading.Text="Die Microsoft WebView2-Runtime fehlt. Bitte die Evergreen Runtime von Microsoft installieren.\nhttps://developer.microsoft.com/microsoft-edge/webview2/";
   }catch(Exception e){if(!closed&&!closing){loading.Text="Start fehlgeschlagen: "+e.Message;Program.ReportError(e);}}
  }
  bool IsOwnPage(string value) { return Uri.TryCreate(value,UriKind.Absolute,out var u)&&backend.Address!=null&&u.Scheme=="http"&&u.Host=="127.0.0.1"&&u.Port==backend.Address.Port; }
  async Task<bool> IsBusy() {
   if(!ready)return false;
   try{return await view.ExecuteScriptAsync("typeof busy !== 'undefined' && busy")=="true";}catch{return false;}
  }
  async void ClosingAsync(object sender,FormClosingEventArgs e) {
   if(allowClose)return;e.Cancel=true;if(closing)return;closing=true;
   if(await IsBusy()) { closing=false;await view.ExecuteScriptAsync("status('Bitte die laufende Anfrage erst abschließen lassen. Danach kannst du die App schließen.', true)");return; }
   closing=true;SaveWindow();await backend.StopAsync();allowClose=true;Close();
  }
  async Task OpenComposition() {
   if(!ready||await IsBusy())return;
   using(var dialog=new OpenFileDialog { Filter="Maestro-Arbeitsstand (*.json)|*.json",Multiselect=false }) {
    if(dialog.ShowDialog(this)!=DialogResult.OK)return;
    try {
     if(new FileInfo(dialog.FileName).Length>28000000)throw new InvalidOperationException("Die Datei ist zu groß.");
     var text=File.ReadAllText(dialog.FileName,Encoding.UTF8);
     view.CoreWebView2.PostWebMessageAsJson(Program.Json.Serialize(new { type="open-composition",text }));
    }catch(Exception e){Program.ReportError(e);}
   }
  }
  async Task SaveDiagnostics() {
   try {
    object service=ready?Program.Json.DeserializeObject(await backend.PostAsync("desktop/info","{}")):(object)"Nicht bereit";
    var diagnostic=new { app="Maestro Composition Lab",version=Program.Version,date=DateTime.Now.ToString("s"),windows=Environment.OSVersion.ToString(),is64bit=Environment.Is64BitProcess,webview=ready?view.CoreWebView2.Environment.BrowserVersionString:"Nicht bereit",service };
    using(var dialog=new SaveFileDialog { FileName="Maestro-App-Diagnose.json",Filter="JSON|*.json" }) {
     if(dialog.ShowDialog(this)==DialogResult.OK)File.WriteAllText(dialog.FileName,Program.Json.Serialize(diagnostic),Encoding.UTF8);
    }
   }catch(Exception e){Program.ReportError(e);}
  }
  void CreateShortcut() {
   try {
    var type=Type.GetTypeFromProgID("WScript.Shell");dynamic shell=Activator.CreateInstance(type);
    dynamic link=shell.CreateShortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"Maestro Composition Lab.lnk"));
    link.TargetPath=Application.ExecutablePath;link.WorkingDirectory=Program.Root;link.Description="Maestro Composition Lab";link.Save();
    MessageBox.Show("Die App ist jetzt im Windows-Startmenü verfügbar.",Text);
    Marshal.FinalReleaseComObject(link);Marshal.FinalReleaseComObject(shell);
   }catch(Exception e){Program.ReportError(e);}
  }
  void RestoreBoundsFromFile() {
   try {
    if(!File.Exists(windowFile))return;
    var s=Program.Json.Deserialize<WindowSettings>(File.ReadAllText(windowFile));
    var rect=new Rectangle(s.X,s.Y,Math.Max(760,s.Width),Math.Max(580,s.Height));
    if(Screen.AllScreens.Any(screen=>Rectangle.Intersect(screen.WorkingArea,rect).Width>150&&Rectangle.Intersect(screen.WorkingArea,rect).Height>150)) {StartPosition=FormStartPosition.Manual;Bounds=rect;}
    if(s.Maximized)WindowState=FormWindowState.Maximized;
   }catch{}
  }
  void SaveWindow() {
   try {var r=WindowState==FormWindowState.Normal?Bounds:RestoreBounds;File.WriteAllText(windowFile,Program.Json.Serialize(new WindowSettings { X=r.X,Y=r.Y,Width=r.Width,Height=r.Height,Maximized=WindowState==FormWindowState.Maximized }),Encoding.UTF8);}catch{}
  }
 }
}
