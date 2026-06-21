#Requires -Version 5.1
# PC helpers for Bike Train Transit Pythonista LAN debug server.
#
#   .\BikeTrainTransit-Windows.ps1 -Action open
#   .\BikeTrainTransit-Windows.ps1 -Action status
#   .\BikeTrainTransit-Windows.ps1 -Action refresh

param(
    [ValidateSet('open', 'status', 'refresh', 'show-config')]
    [string] $Action = 'open',
    [string] $PhoneHost = ''
)

function Get-BikeTrainTransitWindowsConfigPath {
    Join-Path $PSScriptRoot 'bike-train-transit-windows.json'
}

function Get-BikeTrainTransitWindowsExamplePath {
    Join-Path $PSScriptRoot 'bike-train-transit-windows.example.json'
}

function Get-DefaultBikeTrainTransitWindowsSettings {
    [ordered]@{
        phoneLanHost     = ''
        lanDebugPort     = 8765
        iCloudDownloads  = ''
        notes            = ''
    }
}

function Resolve-BikeTrainTransitPath {
    param([string] $Path)
    $t = $Path.Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace($t)) { return '' }
    return [System.IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables(
            ($t -replace '/', [System.IO.Path]::DirectorySeparatorChar)
        )
    )
}

function Read-BikeTrainTransitWindowsConfigFile {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
        return $raw | ConvertFrom-Json
    } catch {
        Write-Warning "Could not parse $Path : $($_.Exception.Message)"
        return $null
    }
}

function Merge-BikeTrainTransitWindowsSettings {
    param($FromFile)
    $merged = Get-DefaultBikeTrainTransitWindowsSettings
    if ($null -eq $FromFile) { return $merged }
    foreach ($prop in $FromFile.PSObject.Properties) {
        if ($merged.Contains($prop.Name)) {
            $merged[$prop.Name] = $prop.Value
        }
    }
    return $merged
}

function Get-BikeTrainTransitWindowsSettings {
    $path = Get-BikeTrainTransitWindowsConfigPath
    $fromFile = Read-BikeTrainTransitWindowsConfigFile -Path $path
    Merge-BikeTrainTransitWindowsSettings -FromFile $fromFile
}

function Get-BikeTrainTransitPhoneHost {
    param([string] $Override = '')
    if (-not [string]::IsNullOrWhiteSpace($Override)) { return $Override.Trim() }
    $s = Get-BikeTrainTransitWindowsSettings
    return [string]$s.phoneLanHost
}

function Get-BikeTrainTransitLanDebugUrl {
    param([string] $PhoneHost = '')
    $s = Get-BikeTrainTransitWindowsSettings
    $ip = Get-BikeTrainTransitPhoneHost -Override $PhoneHost
    if ([string]::IsNullOrWhiteSpace($ip)) {
        throw "Set phoneLanHost in windows\bike-train-transit-windows.json (copy from bike-train-transit-windows.example.json)."
    }
    $port = [int]$s.lanDebugPort
    if ($port -le 0) { $port = 8765 }
    return "http://${ip}:${port}/"
}

function Open-BikeTrainTransitDebug {
    param([string] $PhoneHost = '')
    $url = Get-BikeTrainTransitLanDebugUrl -PhoneHost $PhoneHost
    Write-Host "Opening $url"
    Start-Process $url
}

function Get-BikeTrainTransitDebugStatus {
    param([string] $PhoneHost = '')
    $base = Get-BikeTrainTransitLanDebugUrl -PhoneHost $PhoneHost
    $url = ($base.TrimEnd('/')) + '/status.json'
    Invoke-RestMethod -Uri $url -TimeoutSec 10
}

function Request-BikeTrainTransitRefresh {
    param([string] $PhoneHost = '')
    $base = Get-BikeTrainTransitLanDebugUrl -PhoneHost $PhoneHost
    $url = ($base.TrimEnd('/')) + '/refresh'
    Invoke-RestMethod -Uri $url -TimeoutSec 10
}

function Show-BikeTrainTransitWindowsConfig {
    $s = Get-BikeTrainTransitWindowsSettings
    Write-Host "Bike Train Transit Windows config:"
    Write-Host "  phoneLanHost:    $($s.phoneLanHost)"
    Write-Host "  lanDebugPort:    $($s.lanDebugPort)"
    Write-Host "  iCloudDownloads: $(if ($s.iCloudDownloads) { $s.iCloudDownloads } else { '(default in deploy.ps1)' })"
    try {
        Write-Host "  LAN debug URL:   $(Get-BikeTrainTransitLanDebugUrl)"
    } catch {
        Write-Host "  LAN debug URL:   (set phoneLanHost first)"
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    switch ($Action) {
        'open'        { Open-BikeTrainTransitDebug -PhoneHost $PhoneHost }
        'status'      { Get-BikeTrainTransitDebugStatus -PhoneHost $PhoneHost | ConvertTo-Json -Depth 6 }
        'refresh'     { Request-BikeTrainTransitRefresh -PhoneHost $PhoneHost | ConvertTo-Json -Depth 6 }
        'show-config' { Show-BikeTrainTransitWindowsConfig }
    }
}
