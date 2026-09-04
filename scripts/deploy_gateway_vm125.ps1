# deploy_gateway_vm125.ps1
# AlphaCAM Gateway deployment for vm125 (Win10-alphacam)
# Run via RDP on vm125 as administrator

$ErrorActionPreference = "Stop"
$GatewayDir = "C:\alphacam_cli"
$PythonVersion = "3.12.7"
$PythonInstaller = "C:\temp\python-installer.exe"
$NssmDir = "C:\temp\nssm"
$ServiceName = "AlphaCAMGateway"

Write-Host "=== AlphaCAM Gateway Deployment ===" -ForegroundColor Cyan

# 1. Create temp dir
Write-Host "[1/7] Creating temp directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "C:\temp" -Force | Out-Null

# 2. Download Python if not installed
Write-Host "[2/7] Checking Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python -and (python --version 2>&1 | Select-String "3.1")) {
    Write-Host "  Python already installed: $(python --version)" -ForegroundColor Green
} else {
    Write-Host "  Downloading Python $PythonVersion..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $PythonInstaller -UseBasicParsing
    Write-Host "  Installing Python (silent)..." -ForegroundColor Yellow
    Start-Process -FilePath $PythonInstaller -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Host "  Python installed" -ForegroundColor Green
}

# Verify Python
python --version
pip --version

# 3. Download NSSM (service wrapper)
Write-Host "[3/7] Downloading NSSM..." -ForegroundColor Yellow
if (-not (Test-Path "$NssmDir\nssm.exe")) {
    New-Item -ItemType Directory -Path $NssmDir -Force | Out-Null
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $nssmZip = "C:\temp\nssm.zip"
    Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing
    Expand-Archive -Path $nssmZip -DestinationPath "C:\temp\nssm_extract" -Force
    Copy-Item "C:\temp\nssm_extract\nssm-2.24\win64\nssm.exe" $NssmDir
    Remove-Item "C:\temp\nssm_extract" -Recurse -Force
    Remove-Item $nssmZip -Force
    Write-Host "  NSSM ready" -ForegroundColor Green
} else {
    Write-Host "  NSSM already present" -ForegroundColor Green
}

# 4. Clone / update repo
Write-Host "[4/7] Getting alphacam_cli code..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  Git not found, downloading install..." -ForegroundColor Yellow
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.46.0.windows.1/Git-2.46.0-64-bit.exe"
    $gitInstaller = "C:\temp\git-installer.exe"
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitInstaller -UseBasicParsing
    Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

if (Test-Path "$GatewayDir\.git") {
    Write-Host "  Updating existing repo..." -ForegroundColor Yellow
    Set-Location $GatewayDir
    git pull origin main
} else {
    Write-Host "  Cloning repo..." -ForegroundColor Yellow
    git clone https://github.com/xmichal88x/alphacam_cli.git $GatewayDir
}
Set-Location $GatewayDir

# 5. Create venv and install
Write-Host "[5/7] Installing Python dependencies..." -ForegroundColor Yellow
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
Write-Host "  Dependencies installed" -ForegroundColor Green

# 6. Stop old service if exists
Write-Host "[6/7] Setting up Windows service..." -ForegroundColor Yellow
& "$NssmDir\nssm.exe" stop $ServiceName 2>$null
& "$NssmDir\nssm.exe" remove $ServiceName confirm 2>$null

# Install service
$pythonExe = "$GatewayDir\.venv\Scripts\python.exe"

# Use the gateway service entry point
& "$NssmDir\nssm.exe" install $ServiceName $pythonExe
& "$NssmDir\nssm.exe" set $ServiceName AppParameters "-m alphacam_cli.gateway.service 0.0.0.0 8721"
& "$NssmDir\nssm.exe" set $ServiceName AppDirectory $GatewayDir
& "$NssmDir\nssm.exe" set $ServiceName DisplayName "AlphaCAM Gateway"
& "$NssmDir\nssm.exe" set $ServiceName Description "AlphaCAM COM automation gateway on port 8721"
& "$NssmDir\nssm.exe" set $ServiceName Start SERVICE_AUTO_START
& "$NssmDir\nssm.exe" set $ServiceName ObjectName LocalSystem
& "$NssmDir\nssm.exe" set $ServiceName AppStdout "$GatewayDir\gateway_stdout.log"
& "$NssmDir\nssm.exe" set $ServiceName AppStderr "$GatewayDir\gateway_stderr.log"
& "$NssmDir\nssm.exe" set $ServiceName AppRotateFiles 1
& "$NssmDir\nssm.exe" set $ServiceName AppRotateBytes 1048576

# 7. Open firewall port BEFORE starting service
Write-Host "[7/7] Opening firewall port 8721..." -ForegroundColor Yellow
$existingRule = Get-NetFirewallRule -DisplayName "AlphaCAM Gateway" -ErrorAction SilentlyContinue
if ($existingRule) {
    Remove-NetFirewallRule -DisplayName "AlphaCAM Gateway"
}
New-NetFirewallRule -DisplayName "AlphaCAM Gateway" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8721
Write-Host "  Firewall rule added" -ForegroundColor Green

# 8. Start service
Write-Host "[8/8] Starting gateway service..." -ForegroundColor Yellow
& "$NssmDir\nssm.exe" start $ServiceName

Start-Sleep -Seconds 5
$status = & "$NssmDir\nssm.exe" status $ServiceName
Write-Host "`n=== Service Status ===" -ForegroundColor Cyan
Write-Host "  $status"

if ($status -match "SERVICE_RUNNING") {
    Write-Host "`n  Gateway is RUNNING on port 8721" -ForegroundColor Green
    Write-Host "  Test: from Linux: alphacam --remote --host 192.168.100.60 connect info" -ForegroundColor Gray
} else {
    Write-Host "`n  WARNING: Service may not have started correctly" -ForegroundColor Red
    Write-Host "  Check logs: $GatewayDir\gateway_stderr.log" -ForegroundColor Yellow
}

Write-Host "`nDone!" -ForegroundColor Green
