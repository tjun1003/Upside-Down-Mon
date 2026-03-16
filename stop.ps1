Write-Host "Stopping listeners on ports 8000 and 3000..." -ForegroundColor Yellow

$ports = @(8000, 3000)
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Host ("No listener on port {0}" -f $port) -ForegroundColor DarkGray
        continue
    }

    $processIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $processIds) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host ("Stopped PID {0} on port {1}" -f $processId, $port) -ForegroundColor Green
        } catch {
            Write-Host ("Failed to stop PID {0} on port {1}: {2}" -f $processId, $port, $_.Exception.Message) -ForegroundColor Red
        }
    }
}
