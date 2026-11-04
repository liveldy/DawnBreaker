$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;
public static class DawnWallpaperLayer {
 delegate bool EnumProc(IntPtr h,IntPtr l);
 [DllImport("user32.dll")]static extern IntPtr FindWindow(string c,string n);
 [DllImport("user32.dll")]static extern IntPtr FindWindowEx(IntPtr p,IntPtr a,string c,string n);
 [DllImport("user32.dll")]static extern bool EnumWindows(EnumProc p,IntPtr l);
 [DllImport("user32.dll")]static extern IntPtr SendMessageTimeout(IntPtr h,uint m,IntPtr w,IntPtr l,uint f,uint t,out IntPtr r);
 [DllImport("user32.dll",SetLastError=true)]static extern IntPtr SetParent(IntPtr h,IntPtr p);
 [DllImport("user32.dll")]static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll")]static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")]static extern bool ScreenToClient(IntPtr h,ref Point p);
 [DllImport("user32.dll")]static extern bool SetWindowPos(IntPtr h,IntPtr a,int x,int y,int w,int v,uint f);
 [DllImport("user32.dll")]static extern int GetWindowLong(IntPtr h,int n);
 [DllImport("user32.dll")]static extern int SetWindowLong(IntPtr h,int n,int v);
 struct Rect{public int l,t,r,b;}struct Point{public int x,y;}
 public static void Attach(long[] handles,int owner){IntPtr result;var prog=FindWindow("Progman",null);SendMessageTimeout(prog,0x052C,IntPtr.Zero,IntPtr.Zero,0,1000,out result);IntPtr worker=IntPtr.Zero;EnumWindows((h,l)=>{if(FindWindowEx(h,IntPtr.Zero,"SHELLDLL_DefView",null)!=IntPtr.Zero)worker=FindWindowEx(IntPtr.Zero,h,"WorkerW",null);return true;},IntPtr.Zero);if(worker==IntPtr.Zero)worker=FindWindowEx(prog,IntPtr.Zero,"WorkerW",null);if(worker==IntPtr.Zero)throw new Exception("No WorkerW");foreach(long n in handles){var h=new IntPtr(n);uint pid;GetWindowThreadProcessId(h,out pid);if(pid!=owner)throw new Exception("Owner mismatch");Rect r;GetWindowRect(h,out r);var point=new Point{x=r.l,y=r.t};ScreenToClient(worker,ref point);SetWindowLong(h,-16,(GetWindowLong(h,-16)&~unchecked((int)0x80000000))|0x40000000);SetParent(h,worker);SetWindowPos(h,IntPtr.Zero,point.x,point.y,r.r-r.l,r.b-r.t,0x0410);}}
}
'@
[DawnWallpaperLayer]::Attach([long[]](ConvertFrom-Json 'HANDLES_JSON'), OWNER_PID)
Write-Output 'attached'
