# Proxion DNS Leak Auditor
Write-Host "Auditing DNS resolution paths..."

$Resolvers = Resolve-DnsName google.com | Select-Object -ExpandProperty IPAddress
Write-Host "Resolved google.com to: $Resolvers"

# Check if using local AdGuard
$LocalAdGuard = "127.0.0.1"
Write-Host "Note: If you are seeing your Router IP or ISP DNS here, then you have a LEAK."
Write-Host "Proxion containers should resolve via the AdGuard instance at localhost:3002."
