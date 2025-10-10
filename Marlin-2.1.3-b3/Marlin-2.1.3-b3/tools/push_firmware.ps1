param(
  #[string]$SourceDir = "$PSScriptRoot\firmware\STM32G0B1RE_btt",
  [string]$SourceDir = ".\firmware\STM32G0B1RE_btt",
  # Accept "F", "F:", or "F:\" — we normalize it
  [string]$DriveLetter = "E"
)

$ErrorActionPreference = "Stop"

# --- Normalize drive letter safely (avoid "$DriveLetter:" interpolation issue) ---
$dl = ($DriveLetter.Trim().TrimEnd('\','/',' ')).TrimEnd(':')
if (-not $dl) { throw "DriveLetter is empty." }
$dl = $dl.Substring(0,1).ToUpper()
$DriveRoot = "{0}:\\" -f $dl   # e.g. "F:\"

# --- Validate paths ---
if (-not (Test-Path -LiteralPath $SourceDir)) {
  throw "SourceDir not found: $SourceDir"
}
if (-not (Test-Path -LiteralPath $DriveRoot)) {
  throw "Drive $dl`: not found or not mounted."
}

# --- Find the smallest firmwareNNN.bin by numeric NNN ---
$files =
  Get-ChildItem -LiteralPath $SourceDir -Filter "firmware*.bin" |
  Where-Object { $_.Name -match '^firmware(\d{3})\.bin$' } |
  ForEach-Object {
    $m = [regex]::Match($_.Name, '^firmware(\d{3})\.bin$')
    [pscustomobject]@{
      N     = [int]$m.Groups[1].Value
      Item  = $_
    }
  } |
  Sort-Object N

if (-not $files -or $files.Count -eq 0) {
  throw "No files matching firmwareNNN.bin found in $SourceDir"
}

$first = $files[0]
$nnn   = '{0:D3}' -f $first.N
$src   = $first.Item.FullName

# --- 1) Copy to USB as firmware.bin ---
$destPath = Join-Path $DriveRoot 'firmware.bin'
Copy-Item -LiteralPath $src -Destination $destPath -Force
Write-Host "Copied -> $destPath"

# --- 2) Rename source to NNN-firmware.bin (in-place) ---
$renamedName = "$nnn-firmware.bin"
Rename-Item -LiteralPath $src -NewName $renamedName
Write-Host "Renamed source -> $(Join-Path $SourceDir $renamedName)"

# Optional: brief delay to ensure write completes on slow media
Start-Sleep -Milliseconds 500

# --- 3) Eject the USB drive ---
try {
  $shell = New-Object -ComObject Shell.Application
  $ns = $shell.NameSpace(17)  # "This PC"
  $driveItem = $ns.ParseName(("{0}:" -f $dl))
  if ($driveItem) {
    $driveItem.InvokeVerb("Eject")
    Write-Host "Eject command sent to drive $dl`:"
  } else {
    Write-Warning "Could not access $dl`: for eject (is it removable?)."
  }
} catch {
  Write-Warning "Eject failed: $($_.Exception.Message)"
}
