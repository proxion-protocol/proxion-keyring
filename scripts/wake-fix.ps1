# Proxion Network Wake Recovery Script
# Triggered by Windows Event Log (Source: Power-Troubleshooter, EventID: 107)

Write-Host "Proxion: System wake detected. Initiating network recovery..."

# 1. Reset the physical adapter to clear any S3 link hang
Write-Host "Resetting Ethernet adapter..."
Restart-NetAdapter -Name "Ethernet" -Confirm:$false

# 2. Wait for IP address assignment
Write-Host "Waiting for IP assignment..."
$timeout = 10
while (((Get-NetIPAddress -InterfaceAlias "Ethernet" -AddressFamily IPv4).IPAddress -eq $null) -and ($timeout -gt 0)) {
    Start-Sleep -Seconds 1
    $timeout--
}

# 3. Restart WireGuard Manager
# This forces the Wintun interfaces to re-instantiate
Write-Host "Restarting WireGuard services..."
Stop-Service WireGuardManager -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Start-Service WireGuardManager -ErrorAction SilentlyContinue

# 4. Success Check
if (Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet) {
    Write-Host "Proxion: Internet connectivity restored successfully."
}
else {
    Write-Warning "Proxion: Physical internet restored, but 8.8.8.8 is unreachable."
}
