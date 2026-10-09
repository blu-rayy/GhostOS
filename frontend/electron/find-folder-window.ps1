# Controlled-demo helper for the desktop Pip animation (Windows only).
# Finds the File Explorer window showing $env:GHOSTOS_ROOT, brings it to the front,
# and reports the on-screen box of the item named $env:GHOSTOS_TARGET inside it
# (or, when GHOSTOS_TARGET is empty, the boxes of every visible item).
# Read-only: it never clicks, types, moves, resizes or scrolls anything, and never
# touches files. Inputs come from environment variables, never from the command line.
# Prints one line of JSON. Rectangles are physical pixels (Electron converts to DIP).
$ErrorActionPreference = 'Stop'
try {
  Add-Type @'
using System; using System.Runtime.InteropServices;
public static class GhostWin {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
'@
  [GhostWin]::SetProcessDPIAware() | Out-Null

  $root = $env:GHOSTOS_ROOT.TrimEnd('\')
  $target = $env:GHOSTOS_TARGET
  $match = $null
  foreach ($w in @((New-Object -ComObject Shell.Application).Windows())) {
    try {
      $path = ([uri]$w.LocationURL).LocalPath.TrimEnd('\')
      if ([string]::Equals($path, $root, [StringComparison]::OrdinalIgnoreCase)) { $match = $w; break }
    } catch {}
  }
  if (-not $match) { '{"found":false,"reason":"no Explorer window on that folder"}'; exit 0 }

  $h = [IntPtr]$match.HWND
  if ([GhostWin]::IsIconic($h)) { [GhostWin]::ShowWindow($h, 9) | Out-Null } # SW_RESTORE
  $raised = [GhostWin]::SetForegroundWindow($h)
  Start-Sleep -Milliseconds 350 # let Explorer repaint and pick up the new folders

  $r = New-Object GhostWin+RECT
  [GhostWin]::GetWindowRect($h, [ref]$r) | Out-Null
  $win = @{ x = $r.L; y = $r.T; width = $r.R - $r.L; height = $r.B - $r.T }

  Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
  $A = [Windows.Automation.AutomationElement]
  $listItem = New-Object Windows.Automation.PropertyCondition($A::ControlTypeProperty, [Windows.Automation.ControlType]::ListItem)

  # No target: list every visible item (name + box), for the "reading" animation.
  if (-not $target) {
    $items = @()
    foreach ($el in $A::FromHandle($h).FindAll([Windows.Automation.TreeScope]::Descendants, $listItem)) {
      if ($el.Current.IsOffscreen) { continue }
      $b = $el.Current.BoundingRectangle
      $items += @{ name = $el.Current.Name; x = [int]$b.X; y = [int]$b.Y; width = [int]$b.Width; height = [int]$b.Height }
    }
    @{ found = $true; raised = $raised; window = $win; items = $items } | ConvertTo-Json -Compress -Depth 4
    exit 0
  }

  $cond = New-Object Windows.Automation.AndCondition(
    (New-Object Windows.Automation.PropertyCondition($A::ControlTypeProperty, [Windows.Automation.ControlType]::ListItem)),
    (New-Object Windows.Automation.PropertyCondition($A::NameProperty, $target)))
  $item = $null
  $el = $A::FromHandle($h).FindFirst([Windows.Automation.TreeScope]::Descendants, $cond)
  if ($el -and -not $el.Current.IsOffscreen) {
    $b = $el.Current.BoundingRectangle
    $item = @{ x = [int]$b.X; y = [int]$b.Y; width = [int]$b.Width; height = [int]$b.Height }
  }
  @{ found = $true; raised = $raised; window = $win; item = $item } | ConvertTo-Json -Compress
} catch {
  @{ found = $false; reason = $_.Exception.Message } | ConvertTo-Json -Compress
}
