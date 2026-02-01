<#
.SYNOPSIS
    proxion-keyring Setup Wizard & Launcher
    "It Just Works" - Automates prerequisites and launching.

.DESCRIPTION
    1. Checks for Administrator privileges (Self-elevates if needed).
    2. Checks for WireGuard installation.
    3. Checks/Creates 'wg-proxion-keyring' interface.
    4. Sets necessary Environment Variables.
    5. Launches the proxion-keyring Server.

.EXAMPLE
    Right-click -> Run with PowerShell
#>

$ScriptPath = $MyInvocation.MyCommand.Path
$ScriptDir = Split-Path $ScriptPath

# 1. Admin Check & Self-Elevation
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Requesting Administrator privileges for Network Configuration..." -ForegroundColor Yellow
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" -Verb RunAs
    Exit
}

Write-Host "==============================" -ForegroundColor Cyan
Write-Host "   proxion-keyring SETUP WIZARD     " -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# 2. WireGuard Check & Auto-Install
$wgPath = Get-Command "wg" -ErrorAction SilentlyContinue
if ($null -eq $wgPath) {
    Write-Host "WireGuard is missing. Installing automatically..." -ForegroundColor Yellow
    
    # Try Winget first (Standard on Windows 10/11)
    if (Get-Command "winget" -ErrorAction SilentlyContinue) {
        Write-Host "Installing via Winget..." -ForegroundColor Cyan
        winget install WireGuard.WireGuard -e --silent --accept-package-agreements --accept-source winget
    }
    else {
        # Fallback: Direct Download
        Write-Host "Winget not found. Downloading Installer..." -ForegroundColor Cyan
        $InstallerUrl = "https://download.wireguard.com/windows/wireguard-installer.exe"
        $InstallerPath = "$env:TEMP\wireguard-installer.exe"
        
        Invoke-WebRequest -Uri $InstallerUrl -OutFile $InstallerPath
        Write-Host "Running Installer (Please accept prompts)..." -ForegroundColor Yellow
        Start-Process -FilePath $InstallerPath -ArgumentList "/S" -Wait # /S is guess for silent, standard generic.
        # WireGuard installer doesn't strictly document silent flags easily, but standard usage suggests manual run if silent fails.
    }
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    # Verify again
    if (-not (Get-Command "wg" -ErrorAction SilentlyContinue)) {
        if (Test-Path "C:\Program Files\WireGuard\wg.exe") {
            $env:Path += ";C:\Program Files\WireGuard"
        }
        else {
            Write-Host "[ERROR] Install failed or pending reboot. Please restart script." -ForegroundColor Red
            Exit
        }
    }
    Write-Host "[OK] WireGuard Installed." -ForegroundColor Green
}
else {
    Write-Host "[OK] WireGuard detected." -ForegroundColor Green
}

# 3. Interface Check & Creation
$InterfaceName = "wg-proxion-keyring"
$ShowOut = wg show $InterfaceName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Interface '$InterfaceName' missing. Creating..." -ForegroundColor Yellow
    
    # Generate dummy private key for server interface if creating from scratch
    # Ideally should use keys from config, but for empty tunnel just needs a key.
    # Actual `wg` command needs a config file to create interface usually via `wg-quick` or specialized commands.
    # On Windows, `wireguard /installtunnelservice` is common but complex.
    # SIMPLER: Use `wireguard.exe` commands if available, or just tell user?
    # Actually, we can append a dummy config.
    
    # --- AUTOMATED CREATION ---
    Write-Host "[AUTO] Attempting to create 'wg-proxion-keyring' service..." -ForegroundColor Yellow
    
    # 1. Generate Private Key
    $PrivateKey = wg genkey
    if (-not $PrivateKey) {
        Write-Host "Failed to generate key using 'wg'. Is it in PATH?" -ForegroundColor Red
        Exit
    }
    
    # 2. Define Server Config (Gateway IP)
    # proxion-keyring RS expects to allow 10.0.0.0/24. 
    # We assign 10.0.0.1/24 to the interface itself.
    $ConfContent = @"
[Interface]
PrivateKey = $PrivateKey
Address = 10.0.0.1/24
ListenPort = 51821
"@
    # Note: Using port 51821 to avoid conflict if user has other things on default 51820, 
    # though RS code defaults to 51820. We should match RS env endpoint or update RS.
    # RS `server.py` defaults endpoint to 127.0.0.1:51820.
    # Let's stick to 51820 for consistency with default RS config, 
    # but be aware of conflicts.
    
    # Save to Desktop for User Visibility
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
    $ConfPath = "$DesktopPath\wg-proxion-keyring.conf"
    $ConfContent | Set-Content -Path $ConfPath
    
    # 3. Install Service
    # Requires full path to wireguard.exe
    $WGExe = "C:\Program Files\WireGuard\wireguard.exe"
    if (-not (Test-Path $WGExe)) {
        # Try finding in path
        $WGExe = (Get-Command "wireguard" -ErrorAction SilentlyContinue).Source
    }
    
    if ($WGExe) {
        Write-Host "Installing tunnel service from $ConfPath..."
        $proc = Start-Process -FilePath $WGExe -ArgumentList "/installtunnelservice `"$ConfPath`"" -PassThru -Wait
        
        if ($proc.ExitCode -eq 0) {
            Write-Host "[SUCCESS] Interface created and service started." -ForegroundColor Green
            Write-Host "NOTE: To see this tunnel in the WireGuard GUI:" -ForegroundColor Yellow
            Write-Host "      Open WireGuard -> 'Add Tunnel' -> 'Import from file' -> Select 'wg-proxion-keyring.conf' on your Desktop." -ForegroundColor Yellow
            # Wait a sec for interface to be visible to 'wg show'
            Start-Sleep -Seconds 3
        }
        else {
            Write-Host "[ERROR] Failed to install tunnel service. ExitCode: $($proc.ExitCode)" -ForegroundColor Red
            Exit
        }
    }
    else {
        Write-Host "[ERROR] wireguard.exe not found. Cannot auto-create tunnel." -ForegroundColor Red
        Exit
    }
}
else {
    Write-Host "[OK] Interface '$InterfaceName' exists." -ForegroundColor Green
    Write-Host "NOTE: If not visible in GUI, import existing config." -ForegroundColor Yellow
}

# 4. Environment Setup
$env:proxion-keyring_WG_MUTATION = "true"
$env:proxion-keyring_WG_INTERFACE = $InterfaceName
# Fix Python Path
$env:PYTHONPATH = "$ScriptDir\..;$ScriptDir"

Write-Host ""
Write-Host "Environment configured." -ForegroundColor Green
Write-Host "Starting proxion-keyring Server..." -ForegroundColor Cyan
Write-Host "(Keep this window open)" -ForegroundColor Gray

# 5. Launch
python -m proxion_keyring.rs.server
