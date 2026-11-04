$ErrorActionPreference = 'Stop'
Add-Type -ReferencedAssemblies System.Windows.Forms,System.Drawing,Accessibility -TypeDefinition @'
using System;using System.Text;using System.Runtime.InteropServices;using System.Windows.Forms;using Accessibility;
public class DawnDesktopInput:Form{
 bool accepted=false;int lastMove=0;long[] surfaces;
 [StructLayout(LayoutKind.Sequential)]struct Device{public ushort page,usage;public uint flags;public IntPtr target;}
 [StructLayout(LayoutKind.Sequential)]struct Point{public int x,y;}
 [DllImport("user32.dll")]static extern IntPtr SetThreadDpiAwarenessContext(IntPtr value);
 [DllImport("user32.dll")]static extern bool RegisterRawInputDevices(Device[] devices,uint count,uint size);
 [DllImport("user32.dll")]static extern uint GetRawInputData(IntPtr input,uint command,IntPtr data,ref uint size,uint header);
 [DllImport("user32.dll")]static extern bool GetCursorPos(out Point point);
 [DllImport("user32.dll")]static extern IntPtr WindowFromPoint(Point point);
 [DllImport("user32.dll")]static extern IntPtr GetAncestor(IntPtr window,uint flags);
 [DllImport("user32.dll")]static extern IntPtr GetParent(IntPtr h);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)]static extern int GetClassName(IntPtr window,StringBuilder name,int size);
 [DllImport("oleacc.dll")]static extern int AccessibleObjectFromPoint(Point point,[MarshalAs(UnmanagedType.Interface)]out IAccessible accessible,[MarshalAs(UnmanagedType.Struct)]out object child);
 static string Class(IntPtr h){var name=new StringBuilder(128);GetClassName(h,name,128);return name.ToString();}
 static bool Desktop(IntPtr h){string c=Class(h);return c=="Progman"||c=="WorkerW";}
 bool Accept(Point point){IntPtr hit=WindowFromPoint(point);if(!Desktop(GetAncestor(hit,2)))return false;string c=Class(hit);if(c=="SysListView32"){try{IAccessible accessible;object child;if(AccessibleObjectFromPoint(point,out accessible,out child)!=0||accessible==null)return false;int role=Convert.ToInt32(accessible.get_accRole(child));if(role!=33&&role!=9&&role!=10)return false;}catch{return false;}}if(c.StartsWith("Chrome")){for(IntPtr at=hit;at!=IntPtr.Zero&&!Desktop(at);at=GetParent(at))if(Array.IndexOf(surfaces,at.ToInt64())>=0)return true;return false;}return c=="SysListView32"||c=="SHELLDLL_DefView"||c=="WorkerW"||c=="Progman";}
 protected override void SetVisibleCore(bool value){base.SetVisibleCore(false);}
 public DawnDesktopInput(int owner,long[] handles){surfaces=handles;SetThreadDpiAwarenessContext(new IntPtr(-4));ShowInTaskbar=false;var device=new Device{page=1,usage=2,flags=0x100,target=Handle};if(!RegisterRawInputDevices(new[]{device},1,(uint)Marshal.SizeOf(typeof(Device))))throw new Exception("Raw input unavailable");var timer=new System.Windows.Forms.Timer{Interval=2000};timer.Tick+=(sender,args)=>{try{using(var process=System.Diagnostics.Process.GetProcessById(owner)){if(process.HasExited)Close();}}catch{Close();}};timer.Start();Console.WriteLine("ready");Console.Out.Flush();}
 void Emit(string type,Point p,string button,int delta){Console.WriteLine("{\"type\":\""+type+"\",\"x\":"+p.x+",\"y\":"+p.y+",\"button\":\""+button+"\",\"delta\":"+delta+"}");Console.Out.Flush();}
 protected override void WndProc(ref Message message){if(message.Msg==0x00ff){uint size=0,header=(uint)(IntPtr.Size==8?24:16);GetRawInputData(message.LParam,0x10000003,IntPtr.Zero,ref size,header);if(size>=header+24&&size<4096){IntPtr data=Marshal.AllocHGlobal((int)size);try{if(GetRawInputData(message.LParam,0x10000003,data,ref size,header)==size&&Marshal.ReadInt32(data)==0){Point p;if(GetCursorPos(out p)){if(Accept(p)){accepted=true;int offset=(int)header;ushort flags=(ushort)Marshal.ReadInt16(data,offset+4);if(flags!=0||unchecked(Environment.TickCount-lastMove)>=16){Emit("mouseMove",p,"",0);lastMove=Environment.TickCount;}if((flags&1)!=0)Emit("mouseDown",p,"left",0);if((flags&2)!=0)Emit("mouseUp",p,"left",0);if((flags&16)!=0)Emit("mouseDown",p,"middle",0);if((flags&32)!=0)Emit("mouseUp",p,"middle",0);if((flags&1024)!=0)Emit("mouseWheel",p,"",Marshal.ReadInt16(data,offset+6));}else if(accepted){Emit("mouseLeave",p,"",0);accepted=false;}}}}finally{Marshal.FreeHGlobal(data);}}}base.WndProc(ref message);}
 [STAThread]public static void Run(int owner,long[] handles){Application.Run(new DawnDesktopInput(owner,handles));}
}
'@
[DawnDesktopInput]::Run(OWNER_PID,[long[]](ConvertFrom-Json 'WALLPAPER_HANDLES'))
