using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace MaestroDesktop {
 public sealed class BackendSession : IDisposable {
  public Process Process { get; private set; }
  public Action<Process> OnStarted { get; set; }
  public Uri Address { get; private set; }
  public string Token { get; private set; }
  public readonly string DataFolder;
  private HttpClient http;
  public BackendSession(string dataFolder) { DataFolder=dataFolder; }
  public async Task StartAsync(string python,string engine) {
   if (!File.Exists(python)||!File.Exists(engine)) throw new FileNotFoundException("Die App ist nicht vollständig entpackt. Bitte die gesamte ZIP entpacken.");
   Directory.CreateDirectory(DataFolder);
   var info=new ProcessStartInfo(python,"\""+engine+"\" --desktop") {
    UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,
    WorkingDirectory=Path.GetDirectoryName(engine),StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8
   };
   info.EnvironmentVariables["PYTHONUNBUFFERED"]="1";
   info.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
   info.EnvironmentVariables["MAESTRO_DATA_DIR"]=DataFolder;
   Process=System.Diagnostics.Process.Start(info);
   OnStarted?.Invoke(Process);
   // Consume stderr without writing provider messages or credentials to a log.
   Process.ErrorDataReceived+=(s,e)=>{};Process.BeginErrorReadLine();
   var lineTask=Task.Run(()=>Process.StandardOutput.ReadLine());
   if (await Task.WhenAny(lineTask,Task.Delay(20000)).ConfigureAwait(false)!=lineTask) throw new TimeoutException("Der lokale App-Dienst startet nicht rechtzeitig.");
   string line=await lineTask.ConfigureAwait(false);
   if (line==null||!line.StartsWith("MAESTRO_DESKTOP ")) throw new InvalidOperationException("Der lokale App-Dienst konnte nicht gestartet werden.");
   var url=Regex.Match(line,"\"url\"\\s*:\\s*\"(http://127\\.0\\.0\\.1:[0-9]+/)\"");
   var token=Regex.Match(line,"\"token\"\\s*:\\s*\"([A-Za-z0-9_-]{16,})\"");
   if(!url.Success||!token.Success)throw new InvalidOperationException("Ungültige Startbestätigung des App-Dienstes.");
   Address=new Uri(url.Groups[1].Value);Token=token.Groups[1].Value;
   http=new HttpClient(new HttpClientHandler { UseProxy=false }) { BaseAddress=Address,Timeout=TimeSpan.FromSeconds(12) };
   http.DefaultRequestHeaders.Add("X-Session",Token);
   using(var response=await http.GetAsync("health").ConfigureAwait(false))response.EnsureSuccessStatusCode();
  }
  public async Task<string> PostAsync(string route,string json) {
   if(http==null)throw new InvalidOperationException("App-Dienst nicht bereit.");
   using(var body=new StringContent(json,Encoding.UTF8,"application/json"))
   using(var response=await http.PostAsync(route.TrimStart('/'),body).ConfigureAwait(false)) {
    string text=await response.Content.ReadAsStringAsync().ConfigureAwait(false);
    if(!response.IsSuccessStatusCode)throw new InvalidOperationException("Lokaler App-Dienst: HTTP "+(int)response.StatusCode);
    return text;
   }
  }
  public async Task StopAsync() {
   var p=Process;if(p==null)return;
   try {
    if(!p.HasExited&&http!=null) { try { await PostAsync("shutdown","{}").ConfigureAwait(false); }catch{} }
    if(!p.HasExited) {
     bool ended=await Task.Run(()=>p.WaitForExit(4000)).ConfigureAwait(false);
     if(!ended)p.Kill();
    }
   }catch(InvalidOperationException){}finally { http?.Dispose();http=null;p.Dispose();Process=null; }
  }
  public void Dispose() { StopAsync().GetAwaiter().GetResult(); }
 }
}
