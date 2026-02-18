# setup.ps1 — Create Python 3.11 venv and install requirements
# Usage: Run from project root in PowerShell: .\setup.ps1

Write-Host "Looking for Python 3.11..."
$pythonExe = $null
$probes = @("py -3.11","python3.11","python3.11.exe","python")

foreach ($p in $probes) {
    try {
        $out = & $p -c "import sys;print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $pythonExe = $out.Trim()
            Write-Host "Found Python executable via: $p -> $pythonExe"
            break
        }
    } catch {
        continue
    }
}

if (-not $pythonExe) {
    Write-Host "Python 3.11 not found on PATH or via the py launcher." -ForegroundColor Yellow
    Write-Host "Options:"
    Write-Host " - Install Python 3.11 from https://www.python.org/downloads/windows/"
    Write-Host " - Or run this script inside WSL where Python 3.11 is available."
    exit 1
}

# Create virtual environment folder
$venvPath = Join-Path (Get-Location) ".venv311"
if (Test-Path $venvPath) {
    Write-Host "Removing existing venv at $venvPath"
    Remove-Item -Recurse -Force $venvPath
}

Write-Host "Creating venv at $venvPath using $pythonExe"
& $pythonExe -m venv $venvPath
if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create venv" -ForegroundColor Red; exit 1 }

$pyInVenv = Join-Path $venvPath "Scripts\python.exe"
Write-Host "Upgrading pip in venv..."
& $pyInVenv -m pip install --upgrade pip setuptools wheel

# Install requirements
if (Test-Path "requirements.txt") {
    Write-Host "Installing Python packages from requirements.txt"
    & $pyInVenv -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pip install reported errors. Inspect output above." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "requirements.txt not found in project root." -ForegroundColor Yellow
}

Write-Host "Setup complete. To use the venv run:" -ForegroundColor Green
Write-Host "  .\\.venv311\\Scripts\\Activate.ps1" -ForegroundColor Cyan
Write-Host "Then run the app (Streamlit recommended):" -ForegroundColor Cyan
Write-Host "  streamlit run streamlit_app.py --server.enableCORS false --server.enableXsrfProtection false" -ForegroundColor Cyan
Write-Host "Or run Flask local interface:" -ForegroundColor Cyan
Write-Host "  python main.py"
