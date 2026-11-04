$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
public static class DawnWindowLayer {
  [DllImport("user32.dll", SetLastError=true)] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  static readonly HashSet<long> windows = new HashSet<long>();
  static readonly object gate = new object();
  static bool stopped;
  static int owner;
  static bool Bottom(long value) {
    uint pid; var h = new IntPtr(value); GetWindowThreadProcessId(h, out pid);
    return pid == owner && SetWindowPos(h, new IntPtr(1), 0, 0, 0, 0, 0x0413);
  }
  public static void Run(int parent) {
    owner = parent;
    var reader = new Thread(() => {
      string line;
      while ((line = Console.ReadLine()) != null) {
        var parts = line.Split(' '); long handle; int id;
        if (parts.Length != 3 || !int.TryParse(parts[0], out id) || !long.TryParse(parts[2], out handle)) continue;
        bool ok = true;
        lock (gate) {
          if (parts[1] == "bottom") { ok = Bottom(handle); if(ok) windows.Add(handle); }
          else if (parts[1] == "remove") windows.Remove(handle);
          else ok = false;
        }
        Console.WriteLine(id + " " + (ok ? "ok" : "error")); Console.Out.Flush();
      }
      stopped = true;
    });
    reader.IsBackground = true; reader.Start();
    while (!stopped) {
      try { if (System.Diagnostics.Process.GetProcessById(parent).HasExited) break; } catch { break; }
      lock (gate) { foreach (long value in windows) Bottom(value); }
      Thread.Sleep(500);
    }
  }
}
'@
[DawnWindowLayer]::Run(PARENT_PROCESS_ID)
