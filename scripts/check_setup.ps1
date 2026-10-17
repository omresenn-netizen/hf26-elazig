# Checks that every tool used in this project is installed and connected.
# Run: powershell -ExecutionPolicy Bypass -File scripts\check_setup.ps1

$ErrorActionPreference = "SilentlyContinue"
function Ok($name, $detail)   { Write-Host "[OK]   $name" -ForegroundColor Green; if ($detail) { Write-Host "       $detail" } }
function Fail($name, $detail) { Write-Host "[FAIL] $name" -ForegroundColor Red;   if ($detail) { Write-Host "       $detail" } }

# 1. Ollama + Gemma 4
$ver = (Invoke-RestMethod http://localhost:11434/api/version).version
if ($ver) { Ok "Ollama running" "version $ver at http://localhost:11434" } else { Fail "Ollama running" "start the Ollama app" }

$models = (Invoke-RestMethod http://localhost:11434/api/tags).models.name
if ($models -contains "gemma4:latest") { Ok "Gemma 4 model installed" ($models -join ", ") } else { Fail "Gemma 4 model installed" "run: ollama pull gemma4" }

$body = @{ model = "gemma4"; prompt = "Reply with exactly: Gemma 4 is ready"; stream = $false; think = $false } | ConvertTo-Json
$sw = [Diagnostics.Stopwatch]::StartNew()
$r = Invoke-RestMethod -Uri http://localhost:11434/api/generate -Method Post -ContentType "application/json" -Body $body -TimeoutSec 300
$sw.Stop()
if ($r.response) { Ok "Gemma 4 answers locally" ("'" + $r.response.Trim() + "' in " + [math]::Round($sw.Elapsed.TotalSeconds, 1) + " s") } else { Fail "Gemma 4 answers locally" }

$ps = (& ollama ps 2>$null | Select-Object -Skip 1) -join " "
if ($ps -match "GPU") { Ok "Gemma runs on GPU" $ps.Trim() }

# 2. GitHub Copilot in VS Code
$copilotDir = Get-ChildItem "$env:LOCALAPPDATA\Programs\Microsoft VS Code" -Recurse -Directory -Filter "copilot*" -Depth 4 | Select-Object -First 1
if ($copilotDir) { Ok "GitHub Copilot Chat (built into VS Code)" $copilotDir.FullName } else { Fail "GitHub Copilot Chat" }

$settings = Get-Content "$env:APPDATA\Code\User\settings.json" -Raw
if ($settings -match "ollamaEndpoint") { Ok "Copilot -> Ollama endpoint configured" "github.copilot.chat.byok.ollamaEndpoint" } else { Fail "Copilot -> Ollama endpoint configured" }

# 3. DevRelay (agent sessions -> DEV / MLH)
$mcp = Get-Content "$env:APPDATA\Code\User\mcp.json" -Raw
if ($mcp -match "devrelay") { Ok "DevRelay connected to VS Code (MCP)" } else { Fail "DevRelay connected to VS Code (MCP)" }
if (Test-Path "$env:USERPROFILE\.devrelay\credentials") { Ok "DevRelay logged in to MLH" } else { Fail "DevRelay logged in to MLH" "run: devrelay login" }

# 4. Git + GitHub
$remote = git remote get-url origin
if ($remote) { Ok "GitHub repo connected" $remote } else { Fail "GitHub repo connected" }
$gh = & "C:\Program Files\GitHub CLI\gh.exe" api user --jq .login
if ($gh) { Ok "GitHub account" $gh }
Ok "Commits so far" ((git rev-list --count HEAD) + " commits")
