# Package bike_train_transit for Pythonista via iCloud Drive Downloads.
#
# Deploy workflow:
#   1. Force quit Pythonista on the iPhone
#   2. Files app: delete the old project folder (Downloads + Pythonista)
#   3. Run:  .\deploy.ps1
#   4. On iPhone: Downloads -> unzip -> copy into Pythonista -> run bike_train_transit.py
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\deploy.ps1
# Non-interactive — runs straight through (no Read-Host prompts).

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectName = Split-Path -Leaf $ProjectRoot
$ZipName = "$ProjectName.zip"
$ICloudDownloads = Join-Path $env:USERPROFILE "iCloudDrive\Downloads"

$configModule = Join-Path $ProjectRoot "windows\BikeTrainTransit-Windows.ps1"
if (Test-Path -LiteralPath $configModule) {
    . $configModule
    $winCfg = Get-BikeTrainTransitWindowsSettings
    if (-not [string]::IsNullOrWhiteSpace([string]$winCfg.iCloudDownloads)) {
        $ICloudDownloads = Resolve-BikeTrainTransitPath ([string]$winCfg.iCloudDownloads)
    }
}
$TempZip = Join-Path $env:TEMP $ZipName
$DestZip = Join-Path $ICloudDownloads $ZipName

$ExcludeDirs = @(
    ".git", "__pycache__", ".cursor", ".vscode", "ai", "archive",
    "bike_train_transit", "citibike_alert", "windows", "tools"
)
$ExcludeFiles = @(
    "*.pyc", "deploy.ps1",
    "bike-train-transit-windows.json",
    "bike_train_transit_alert.py", "config.json",
    ".env", ".env.example"
)

function Write-Step($Message) {
    Write-Host "==> $Message"
}

if (-not (Test-Path $ICloudDownloads)) {
    throw "iCloud Downloads folder not found: $ICloudDownloads"
}

Write-Host ""
Write-Host "Deploy workflow:"
Write-Host "  [YOU] 1. Force quit Pythonista on the iPhone (app switcher -> swipe away)"
Write-Host "  [YOU] 2. Files app: delete the old $ProjectName folder everywhere it exists:"
Write-Host "           - iCloud Drive -> Downloads -> $ProjectName (if present)"
Write-Host "           - Pythonista folder (iCloud or On My iPhone) -> $ProjectName"
Write-Host "  [PC]  3. This script (zip + copy to iCloud Downloads)"
Write-Host "  [YOU] 4. iPhone Files -> Downloads -> unzip -> copy into Pythonista"
Write-Host "           Run bike_train_transit.py once (installs RunBikeTrainTransit.py launcher)"
Write-Host ""

Write-Step "Removing old deploy artifacts from $ICloudDownloads"
foreach ($Name in @($ZipName, $ProjectName)) {
    $OldPath = Join-Path $ICloudDownloads $Name
    if (Test-Path -LiteralPath $OldPath) {
        Write-Host "    removing $OldPath"
        Remove-Item -LiteralPath $OldPath -Recurse -Force
    }
}

Write-Step "Staging project (excluding build/editor junk and PC-only files)"
$StageRoot = Join-Path $env:TEMP ("deploy-stage-" + [guid]::NewGuid().ToString("n"))
$StageDir = Join-Path $StageRoot $ProjectName
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null

$RoboArgs = @(
    $ProjectRoot,
    $StageDir,
    "/E",
    "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS"
)
foreach ($Dir in $ExcludeDirs) {
    $RoboArgs += "/XD"
    $RoboArgs += $Dir
}
foreach ($File in $ExcludeFiles) {
    $RoboArgs += "/XF"
    $RoboArgs += $File
}
& robocopy @RoboArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force -ErrorAction SilentlyContinue
    throw "robocopy failed with exit code $LASTEXITCODE"
}

Write-Step "Creating zip $ZipName"
if (Test-Path $TempZip) {
    Remove-Item -LiteralPath $TempZip -Force
}
Compress-Archive -LiteralPath $StageDir -DestinationPath $TempZip -CompressionLevel Optimal -Force
Remove-Item -LiteralPath $StageRoot -Recurse -Force

Write-Step "Copying zip to iCloud Downloads"
Copy-Item -LiteralPath $TempZip -Destination $DestZip -Force
Remove-Item -LiteralPath $TempZip -Force

$SizeMb = [math]::Round((Get-Item -LiteralPath $DestZip).Length / 1MB, 2)
$MainPy = Join-Path $ProjectRoot "bike_train_transit.py"
$BuildTag = ""
if (Test-Path -LiteralPath $MainPy) {
    $mainText = Get-Content -LiteralPath $MainPy -Raw
    if ($mainText -match 'BUILD_TAG = "([^"]+)"') {
        $BuildTag = $Matches[1]
    }
}
Write-Host ""
Write-Host "Done. $DestZip ($SizeMb MB)"
Write-Host ""
Write-Host "Deployed from: $ProjectRoot"
if ($BuildTag) {
    Write-Host "BUILD_TAG: $BuildTag  (LAN log should show build=$BuildTag after you run on iPhone)"
}
Write-Host ""
Write-Host "Next on iPhone:"
Write-Host "  Files -> iCloud Drive -> Downloads"
Write-Host "  Tap $ZipName to unzip, copy $ProjectName into Pythonista"
Write-Host "  Run bike_train_transit.py once (copies to On This iPhone/Documents)"
Write-Host "  Shortcut URL: pythonista3://bike_train_transit/bike_train_transit.py?action=run"
