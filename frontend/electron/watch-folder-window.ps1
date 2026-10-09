# Desktop Pip helper (Windows only): watches the Explorer window Pip is haunting.
# Read-only: it only asks Windows whether the window still exists, is minimized, or has moved.
# Prints one line of JSON and exits as soon as one of those happens:
#   {"event":"closed"} | {"event":"minimized"} | {"event":"moved"}
# Electron then sends Pip and the progress bar away and falls back to the in-app progress.
# Input comes from an environment variable (GHOSTOS_HWND), never from the command line.
$ErrorActionPreference = 'Stop'
try {
  Add-Type @'
using System; using System.Runtime.InteropServices;
public static class GhostWatch {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
'@
  [GhostWatch]::SetProcessDPIAware() | Out-Null
  $h = [IntPtr][int64]$env:GHOSTOS_HWND
  $start = New-Object GhostWatch+RECT
  [GhostWatch]::GetWindowRect($h, [ref]$start) | Out-Null
  $deadline = (Get-Date).AddMinutes(15) # never outlive a scan by much
  while ((Get-Date) -lt $deadline) {
    if (-not [GhostWatch]::IsWindow($h)) { '{"event":"closed"}'; exit 0 }
    if ([GhostWatch]::IsIconic($h)) { '{"event":"minimized"}'; exit 0 }
    $now = New-Object GhostWatch+RECT
    [GhostWatch]::GetWindowRect($h, [ref]$now) | Out-Null
    # A few pixels of slack: Explorer can nudge its frame when it repaints.
    if ([Math]::Abs($now.L - $start.L) -gt 4 -or [Math]::Abs($now.T - $start.T) -gt 4 -or
        [Math]::Abs($now.R - $start.R) -gt 4 -or [Math]::Abs($now.B - $start.B) -gt 4) { '{"event":"moved"}'; exit 0 }
    Start-Sleep -Milliseconds 250
  }
  '{"event":"timeout"}'
} catch {
  @{ event = 'error'; reason = $_.Exception.Message } | ConvertTo-Json -Compress
}
