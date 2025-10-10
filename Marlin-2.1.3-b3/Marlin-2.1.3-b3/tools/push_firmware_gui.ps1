# tools\push_firmware_gui.ps1
# GUI tool to:
# 1) Find the smallest firmwareNNN.bin in the selected folder
# 2) Copy it to the selected USB drive as firmware.bin
# 3) Rename the source to NNN-firmware.bin
# 4) Optionally eject the USB drive

# --- Relaunch in STA (Windows PowerShell 5.1) and set up WinForms ---
if ($PSVersionTable.PSEdition -eq 'Desktop' -and
    [System.Threading.Thread]::CurrentThread.ApartmentState -ne 'STA')
{
  Write-Host "Re-launching in STA mode..."
  powershell -STA -ExecutionPolicy Bypass -File "$PSCommandPath"
  exit
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
[System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false)

# ---------- Defaults ----------
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DefaultEnv  = 'STM32G0B1RE_btt'
$DefaultSrc  = Join-Path $ProjectRoot (Join-Path 'firmware' $DefaultEnv)

# ---------- Helpers ----------
function Get-RemovableDrives {
  [System.IO.DriveInfo]::GetDrives() |
    Where-Object { $_.DriveType -eq 'Removable' -and $_.IsReady } |
    Select-Object @{n='Letter';e={$_.Name.Substring(0,1)}}, Name
}

function LogLine([System.Windows.Forms.TextBox]$tb, [string]$msg) {
  $tb.AppendText(("[{0}] {1}`r`n" -f (Get-Date -Format 'HH:mm:ss'), $msg))
}

function FindSmallestFirmware([string]$dir) {
  if (-not (Test-Path -LiteralPath $dir)) { return $null }
  $items = Get-ChildItem -LiteralPath $dir -Filter 'firmware*.bin' -File |
    Where-Object { $_.Name -match '^firmware(\d{3})\.bin$' } |
    ForEach-Object {
      $n = [int]([regex]::Match($_.Name, '^firmware(\d{3})\.bin$').Groups[1].Value)
      [pscustomobject]@{ N = $n; Item = $_ }
    } |
    Sort-Object N
  if ($items -and $items.Count -gt 0) { return $items[0] }
  return $null
}

function SafeEjectDrive([string]$letter) {
  try {
    $shell = New-Object -ComObject Shell.Application
    $ns = $shell.NameSpace(17) # "This PC"
    $driveItem = $ns.ParseName(("{0}:" -f $letter))
    if ($driveItem) {
      $driveItem.InvokeVerb("Eject")
      return $true
    }
  } catch { }
  return $false
}

# ---------- UI ----------
$form = New-Object System.Windows.Forms.Form
$form.Text = " Xunda Tech Firmware USB Pusher"
$form.Size = New-Object System.Drawing.Size(640, 420)
$form.StartPosition = 'CenterScreen'

$lblSrc = New-Object System.Windows.Forms.Label
$lblSrc.Text = "Source folder (contains firmwareNNN.bin):"
$lblSrc.AutoSize = $true
$lblSrc.Location = New-Object System.Drawing.Point(12, 15)

$tbSrc = New-Object System.Windows.Forms.TextBox
$tbSrc.Size = New-Object System.Drawing.Size(470, 20)
$tbSrc.Location = New-Object System.Drawing.Point(12, 35)
$tbSrc.Text = $DefaultSrc

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = "Browse..."
$btnBrowse.Location = New-Object System.Drawing.Point(490, 33)
$btnBrowse.Add_Click({
  $fbd = New-Object System.Windows.Forms.FolderBrowserDialog
  $fbd.SelectedPath = $tbSrc.Text
  if ($fbd.ShowDialog() -eq 'OK') { $tbSrc.Text = $fbd.SelectedPath }
})

$lblDrive = New-Object System.Windows.Forms.Label
$lblDrive.Text = "USB Drive:"
$lblDrive.AutoSize = $true
$lblDrive.Location = New-Object System.Drawing.Point(12, 70)

$cbDrive = New-Object System.Windows.Forms.ComboBox
$cbDrive.DropDownStyle = 'DropDownList'
$cbDrive.Location = New-Object System.Drawing.Point(80, 66)
$cbDrive.Width = 70

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text = "Refresh"
$btnRefresh.Location = New-Object System.Drawing.Point(160, 65)

$chkEject = New-Object System.Windows.Forms.CheckBox
$chkEject.Text = "Eject after copy"
$chkEject.Checked = $true
$chkEject.AutoSize = $true
$chkEject.Location = New-Object System.Drawing.Point(250, 67)

$btnOpenSrc = New-Object System.Windows.Forms.Button
$btnOpenSrc.Text = "Open Source Folder"
$btnOpenSrc.Location = New-Object System.Drawing.Point(380, 65)

$btnPush = New-Object System.Windows.Forms.Button
$btnPush.Text = "Push Next Firmware"
$btnPush.Location = New-Object System.Drawing.Point(12, 100)
$btnPush.Width = 180

$tbLog = New-Object System.Windows.Forms.TextBox
$tbLog.Multiline = $true
$tbLog.ReadOnly = $true
$tbLog.ScrollBars = 'Vertical'
$tbLog.Location = New-Object System.Drawing.Point(12, 140)
$tbLog.Size = New-Object System.Drawing.Size(600, 220)
$tbLog.Font = New-Object System.Drawing.Font("Consolas", 9)

$form.Controls.AddRange(@(
  $lblSrc,$tbSrc,$btnBrowse,
  $lblDrive,$cbDrive,$btnRefresh,$chkEject,$btnOpenSrc,
  $btnPush,$tbLog
))

# Populate drives
$populate = {
  $cbDrive.Items.Clear()
  $drives = Get-RemovableDrives
  foreach ($d in $drives) { [void]$cbDrive.Items.Add($d.Letter) }
  if ($cbDrive.Items.Count -gt 0) { $cbDrive.SelectedIndex = 0 }
}
& $populate
$btnRefresh.Add_Click({ & $populate })
$btnOpenSrc.Add_Click({
  if (Test-Path -LiteralPath $tbSrc.Text) {
    Start-Process explorer.exe $tbSrc.Text
  } else {
    [System.Windows.Forms.MessageBox]::Show("Folder not found:`n$($tbSrc.Text)","Open Folder",0,'Error') | Out-Null
  }
})

# Main action
$btnPush.Add_Click({
  try {
    $srcDir = $tbSrc.Text.Trim()
    if (-not (Test-Path -LiteralPath $srcDir)) {
      [System.Windows.Forms.MessageBox]::Show("Source folder not found:`n$srcDir","Error",0,'Error') | Out-Null
      return
    }
    if (-not $cbDrive.SelectedItem) {
      [System.Windows.Forms.MessageBox]::Show("Select a USB drive first.","Error",0,'Error') | Out-Null
      return
    }
    $driveLetter = [string]$cbDrive.SelectedItem
    $driveRoot = "{0}:\\" -f $driveLetter

    if (-not (Test-Path -LiteralPath $driveRoot)) {
      [System.Windows.Forms.MessageBox]::Show("Drive $driveLetter`: not found or not mounted.","Error",0,'Error') | Out-Null
      return
    }

    $next = FindSmallestFirmware -dir $srcDir
    if (-not $next) {
      [System.Windows.Forms.MessageBox]::Show("No firmwareNNN.bin files found in:`n$srcDir","Nothing to do",0,'Information') | Out-Null
      return
    }

    $nnn = '{0:D3}' -f $next.N
    $srcPath = $next.Item.FullName
    $dstPath = Join-Path $driveRoot 'firmware.bin'

    LogLine $tbLog "Copying $($next.Item.Name) -> $dstPath"
    Copy-Item -LiteralPath $srcPath -Destination $dstPath -Force

    $newName = "$nnn-firmware.bin"
    $targetName = Join-Path $srcDir $newName
    if (Test-Path -LiteralPath $targetName) {
      $stamp = (Get-Date -Format 'yyyyMMdd-HHmmss')
      $newName = "$nnn-firmware-$stamp.bin"
    }
    Rename-Item -LiteralPath $srcPath -NewName $newName
    LogLine $tbLog "Renamed source -> $newName"

    if ($chkEject.Checked) {
      $ok = SafeEjectDrive -letter $driveLetter
      if ($ok) { LogLine $tbLog "Eject sent to drive $driveLetter`:" }
      else { LogLine $tbLog "Eject failed or drive not removable." }
    }

    [System.Media.SystemSounds]::Asterisk.Play()
    LogLine $tbLog "Done."
  } catch {
    [System.Media.SystemSounds]::Hand.Play()
    LogLine $tbLog ("ERROR: " + $_.Exception.Message)
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "Error", 0, 'Error') | Out-Null
  }
})

# Enable drag & drop of a folder onto the Source textbox
$tbSrc.AllowDrop = $true
$tbSrc.Add_DragEnter({
  if ($_.Data.GetDataPresent([System.Windows.Forms.DataFormats]::FileDrop)) { $_.Effect = 'Copy' }
})
$tbSrc.Add_DragDrop({
  $paths = $_.Data.GetData([System.Windows.Forms.DataFormats]::FileDrop)
  if ($paths -and (Test-Path -LiteralPath $paths[0])) { $tbSrc.Text = $paths[0] }
})

# Run the WinForms message loop
[System.Windows.Forms.Application]::Run($form)
