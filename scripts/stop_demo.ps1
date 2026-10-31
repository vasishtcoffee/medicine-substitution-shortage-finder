# Stops the demo servers started by start_demo.ps1 (API 8000, web 3000, portable MongoDB 27017). MySQL service is left running.
foreach ($p in 8000, 3000, 27017) {
    Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Write-Host "stopped API, web and MongoDB (if they were running)"
