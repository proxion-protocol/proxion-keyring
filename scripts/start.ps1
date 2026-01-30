# Start Kleitikon Full Stack
# Launches SCS, CP, RS, and Web App in separate windows.

$Root = Get-Location
Write-Host "Starting Kleitikon Stack from $Root..."

# 1. Solid Community Server (Port 3200)
Write-Host "Launching SCS (Port 3200)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; ./scripts/run_scs.ps1"

# 2. Control Plane (Port 8787)
Write-Host "Launching CP (Port 8787)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; python -m cp.server"

# 3. Resource Server (Port 8788)
Write-Host "Launching RS (Port 8788)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; python -m rs.server"

# 4. Web App (Port 5173 - Default)
Write-Host "Launching Web App..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root/app'; npm run dev -- --host"

Write-Host "---------------------------------------------------"
Write-Host "All services started!"
Write-Host "CP: http://127.0.0.1:8787"
Write-Host "RS: http://127.0.0.1:8788"
Write-Host "App: http://localhost:5173"
Write-Host "SCS: http://localhost:3200"
Write-Host "---------------------------------------------------"
