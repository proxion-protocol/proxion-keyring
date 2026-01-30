# Run Solid Community Server (Data in ./data)
# Used for local development and Kleitikon testing.

$Port = 3200
$DataDir = "$(Get-Location)/data"

Write-Host "Starting Solid Community Server on port $Port..."
Write-Host "Data directory: $DataDir"
Write-Host "--------------------------------------------------------"
Write-Host "OPEN: http://localhost:$Port/ in your browser"
Write-Host "1. Output will say 'Listening on port $Port'"
Write-Host "2. Go to http://localhost:$Port/"
Write-Host "3. Click 'Setup' (create an email/password, uncheck 'Enforce Email')"
Write-Host "4. This is a one-time setup per data folder."
Write-Host "--------------------------------------------------------"

# remove -c config (falls back to default with setup wizard, clearer for npx usage on windows)
npx -y @solid/community-server -f ./data -p $Port
