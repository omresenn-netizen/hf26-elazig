$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$ollamaUrl = "http://localhost:11434"
try {
    $ollamaVersion = Invoke-RestMethod -Uri "$ollamaUrl/api/version" -TimeoutSec 5
} catch {
    throw "Ollama is not responding at $ollamaUrl. Start Ollama and run this script again."
}

$models = (Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 10).models
$gemmaInstalled = $false
foreach ($model in $models) {
    if ($model.name -match "^gemma4(?::|$)") {
        $gemmaInstalled = $true
        break
    }
}
if (-not $gemmaInstalled) {
    throw "The gemma4 model is not installed. Run 'ollama pull gemma4' and try again."
}

Write-Host "Ollama $($ollamaVersion.version) is ready with gemma4."

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create .venv. Install Python 3.13 and try again."
    }
}

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "Installing requirements failed."
}

$appUrl = "http://127.0.0.1:8600"
function Test-ApiReady {
    try {
        Invoke-WebRequest -Uri "$appUrl/api/me" -TimeoutSec 2 | Out-Null
        return $false
    } catch {
        if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) {
            return $true
        }
        return $false
    }
}

if (-not (Test-ApiReady)) {
    $logsPath = Join-Path $repoRoot "logs"
    New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
    $stdoutPath = Join-Path $logsPath "server.stdout.log"
    $stderrPath = Join-Path $logsPath "server.stderr.log"
    $server = Start-Process -FilePath $venvPython `
        -ArgumentList @("-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8600") `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        if (Test-ApiReady) {
            $ready = $true
            break
        }
        $server.Refresh()
        if ($server.HasExited) {
            break
        }
    }
    if (-not $ready) {
        $details = if (Test-Path $stderrPath) { Get-Content $stderrPath -Raw } else { "No server log was created." }
        throw "The API did not become ready at $appUrl. $details"
    }
}

Start-Process $appUrl
Write-Host "VadeX is ready at $appUrl"
