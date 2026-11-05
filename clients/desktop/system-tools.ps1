param(
 [Parameter(Mandatory=$true)][ValidateSet('storage','trim-memory')][string]$Action,
 [string]$DataPath,
 [string]$ProcessIds,
 [string]$ExecutablePath
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
if($Action -eq 'storage'){
 $root=[System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($DataPath))
 $drive=New-Object System.IO.DriveInfo($root)
 @{total=[double]$drive.TotalSize;available=[double]$drive.AvailableFreeSpace;name=$drive.Name}|ConvertTo-Json -Compress
 exit
}
if($ProcessIds -notmatch '^\d+(,\d+){0,63}$'){throw 'Invalid process list'}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DawnWorkingSet {
 [DllImport("kernel32.dll",SetLastError=true)] public static extern IntPtr OpenProcess(uint access,bool inherit,int id);
 [DllImport("psapi.dll",SetLastError=true)] public static extern bool EmptyWorkingSet(IntPtr process);
 [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr handle);
}
'@
$processed=0
foreach($value in $ProcessIds.Split(',')){
 $handle=[IntPtr]::Zero
 try{
  $process=[System.Diagnostics.Process]::GetProcessById([int]$value)
  if(-not [string]::Equals($process.MainModule.FileName,$ExecutablePath,[StringComparison]::OrdinalIgnoreCase)){continue}
  $handle=[DawnWorkingSet]::OpenProcess(0x1100,$false,[int]$value)
  if($handle -ne [IntPtr]::Zero -and [DawnWorkingSet]::EmptyWorkingSet($handle)){$processed++}
 }catch{}finally{if($handle -ne [IntPtr]::Zero){[void][DawnWorkingSet]::CloseHandle($handle)}}
}
@{processed_count=$processed}|ConvertTo-Json -Compress
