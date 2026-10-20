using MaestroDesktop;
using System.Text.Json;
using System.Diagnostics;
using System.Net;
using System.Net.Http;

static void Check(bool condition,string message){if(!condition)throw new Exception(message);}
string engine=Path.GetFullPath(args[0]),python=args[1];
string data=Path.Combine(Path.GetTempPath(),"maestro-desktop-test-"+Guid.NewGuid().ToString("N"));
int pid;
try {
 using(var session=new BackendSession(data)) {
  await session.StartAsync(python,Path.Combine(engine,"maestro_analyse.py"));pid=session.Process.Id;
  var info=await session.PostAsync("desktop/info","{}");
  Check(info.Contains("\"desktop\": true"),"Desktop flag missing");Check(info.Contains("3.0.1"),"Version missing");
  using var raw=new HttpClient(new HttpClientHandler {UseProxy=false});
  var html=await raw.GetStringAsync(session.Address);
  Check(!html.Contains("__TOKEN__"),"Session token not inserted");
  using var denied=await raw.PostAsync(new Uri(session.Address,"desktop/info"),new StringContent("{}"));
  Check(denied.StatusCode==HttpStatusCode.Forbidden,"Unguarded desktop endpoint");
  var composition=new {title="Desktop-Test",composer="",time=new[]{2,4},key=new object[]{2,"major"},tempo=116,staves=new[]{new {name="Piano",clef="treble",bars=new[]{new {voices=new object[]{new object[]{new object[]{"h",new[]{"C4"}}}}}}}}};
  var request=JsonSerializer.Serialize(new {text=JsonSerializer.Serialize(composition)});
  var loaded=JsonDocument.Parse(await session.PostAsync("workspace/load",request));
  var id=loaded.RootElement.GetProperty("id").GetString();Check(!string.IsNullOrEmpty(id),"Import failed");
  Check(Directory.GetFiles(Path.Combine(data,"Ergebnisse"),"*.json").Length==1,"Permanent results folder missing");
  await session.StopAsync();
 }
 bool alive;try{using var p=Process.GetProcessById(pid);alive=!p.HasExited;}catch(ArgumentException){alive=false;}
 Check(!alive,"Service orphaned after closing");
 Console.WriteLine("PASS: Native-host BackendSession starts real Python service; handshake/health; authenticated IPC; JSON import; persistent result; clean shutdown without orphan.");
}catch{throw;}finally{if(Directory.Exists(data))Directory.Delete(data,true);}
