using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
namespace MaestroDesktop {
 // Closing the native app also ends its service and helper processes after a crash.
 sealed class OwnedProcessJob : IDisposable {
  [StructLayout(LayoutKind.Sequential)]struct Basic {
   public long ProcessTime,JobTime;public uint Flags;public UIntPtr Min,Max;public uint Active;public UIntPtr Affinity;public uint Priority,Scheduling;
  }
  [StructLayout(LayoutKind.Sequential)]struct Io {public ulong ReadOps,WriteOps,OtherOps,ReadBytes,WriteBytes,OtherBytes;}
  [StructLayout(LayoutKind.Sequential)]struct Limits {public Basic Basic;public Io Io;public UIntPtr ProcessMemory,JobMemory,PeakProcess,PeakJob;}
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern SafeFileHandle CreateJobObject(IntPtr attributes,string name);
  [DllImport("kernel32.dll",SetLastError=true)]static extern bool SetInformationJobObject(SafeFileHandle job,int kind,ref Limits info,uint size);
  [DllImport("kernel32.dll",SetLastError=true)]static extern bool AssignProcessToJobObject(SafeFileHandle job,IntPtr process);
  readonly SafeFileHandle handle;
  public OwnedProcessJob() {
   handle=CreateJobObject(IntPtr.Zero,null);
   if(handle.IsInvalid)throw new Win32Exception(Marshal.GetLastWin32Error());
   var info=new Limits { Basic=new Basic { Flags=0x2000 } };
   if(!SetInformationJobObject(handle,9,ref info,(uint)Marshal.SizeOf(typeof(Limits)))){int error=Marshal.GetLastWin32Error();handle.Dispose();throw new Win32Exception(error);}
  }
  public void Own(Process p) {if(!AssignProcessToJobObject(handle,p.Handle))throw new Win32Exception(Marshal.GetLastWin32Error());}
  public void Dispose(){handle.Dispose();}
 }
}
