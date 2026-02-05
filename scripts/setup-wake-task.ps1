# Proxion: Setup Wake Recovery Task
# Requires Administrative Privileges

$ScriptPath = Join-Path -Path $PSScriptRoot -ChildPath "wake-fix.ps1"

# 1. Disable Ethernet Power Management (PnPCapabilities bit 4)
# This prevents Windows from turning off the card to save power.
Write-Host "Hardware Hardening: Disabling Ethernet power-down..."
$RegistryPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
$AdapterKey = Get-ItemProperty -Path "$RegistryPath\*" | Where-Object { $_.DriverDesc -like "*Realtek*2.5GbE*" } | Select-Object -ExpandProperty PSPath

if ($AdapterKey) {
    # Set PnPCapabilities to 24 (0x18) 
    # bits 3 and 4: Allow wake (up) and Turn off (down)
    Set-ItemProperty -Path $AdapterKey -Name "PnPCapabilities" -Value 24 -Type DWord
    Write-Host "Successfully updated Registry for $AdapterKey"
}
else {
    Write-Warning "Could not find Realtek adapter in registry class list."
}

# 2. Create Scheduled Task
Write-Host "Automation: Creating 'Proxion Wake Recovery' task..."
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -File `"$ScriptPath`""
$Trigger = New-JobTrigger -AtStartup # Placeholder, we'll use CIM for the event log
# New-JobTrigger doesn't easily support Event Log triggers in a simple way, 
# we use Register-ScheduledTask with a custom XML or just raw CIM if possible.
# Simpler: Use schtasks or a specific XML.

$TaskName = "ProxionWakeRecovery"
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=107]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>PowerShell.exe</Command>
      <Arguments>-ExecutionPolicy Bypass -WindowStyle Hidden -File "$ScriptPath"</Arguments>
    </Exec>
  </Actions>
</Task>
"@

# Write XML to temp and import
$TempXml = [System.IO.Path]::GetTempFileName()
$xml | Out-File $TempXml -Encoding UTF8
Register-ScheduledTask -Xml (Get-Content $TempXml | Out-String) -TaskName $TaskName -Force
Remove-Item $TempXml

Write-Host "Task 'ProxionWakeRecovery' registered and ready."
