# Builds the live-backend Windows installer and signs it with the GhostOS code-signing
# certificate. The .pfx and its password live outside the repo, by default in
# %USERPROFILE%\.ghostos-signing\ (override with GHOSTOS_SIGNING_DIR). Never commit them.
#
# Usage (from frontend/):  npm run package:win:signed
#   Pass -Demo to build the demo-data installer instead.
param([switch]$Demo)

$ErrorActionPreference = 'Stop'
$dir = if ($env:GHOSTOS_SIGNING_DIR) { $env:GHOSTOS_SIGNING_DIR } else { Join-Path $env:USERPROFILE '.ghostos-signing' }
$pfx = Join-Path $dir 'ghostos-codesign.pfx'
$pwFile = Join-Path $dir 'pfx-password.txt'

if (-not (Test-Path $pfx) -or -not (Test-Path $pwFile)) {
  throw "Signing certificate not found in $dir (need ghostos-codesign.pfx and pfx-password.txt)."
}

$env:CSC_LINK = $pfx
$env:CSC_KEY_PASSWORD = (Get-Content -Raw $pwFile).Trim()
# VS Code terminals set this, which would make electron-builder's Electron helpers run as plain Node.
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

try {
  if ($Demo) { npm run package:win:demo } else { npm run package:win }
  if ($LASTEXITCODE -ne 0) { throw "Packaging failed (exit $LASTEXITCODE)." }
} finally {
  Remove-Item Env:CSC_LINK, Env:CSC_KEY_PASSWORD -ErrorAction SilentlyContinue
}

$out = if ($Demo) { 'release\demo' } else { 'release' }
Get-ChildItem $out -Filter '*.exe' | ForEach-Object {
  $sig = Get-AuthenticodeSignature $_.FullName
  '{0}: {1} ({2})' -f $_.Name, $sig.Status, $sig.SignerCertificate.Subject
}
