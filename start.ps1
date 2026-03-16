Write-Host "Starting Hackathon project..." -ForegroundColor Cyan
Write-Host ""

function Stop-PortListeners {
	param([int[]]$Ports)

	foreach ($port in $Ports) {
		$conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
		if (-not $conns) {
			continue
		}

		$processIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
		foreach ($processId in $processIds) {
			try {
				Stop-Process -Id $processId -Force -ErrorAction Stop
				Write-Host ("Stopped PID {0} on port {1}" -f $processId, $port) -ForegroundColor DarkYellow
			} catch {
				Write-Host ("Failed to stop PID {0} on port {1}: {2}" -f $processId, $port, $_.Exception.Message) -ForegroundColor Red
			}
		}
	}
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Cleaning old listeners on ports 8000 and 3000..." -ForegroundColor Yellow
Stop-PortListeners -Ports @(8000, 3000)

Write-Host "Starting Python backend on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir\src\app\api\translate'; Write-Host 'Using Conda env Hackathon...' -ForegroundColor Magenta; conda run -n Hackathon --no-capture-output python translation.py"

Write-Host "Starting Next.js frontend on port 3000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir'; Write-Host 'Next.js frontend starting...' -ForegroundColor Green; npm run dev"

Write-Host ""
Write-Host "Services started." -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tip: run npm run stop:all to stop both ports quickly." -ForegroundColor Gray
