# Runs Vadesiz's GitHub Copilot CLI agent team in parallel git worktrees.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\agent_team.ps1 -Agents kobi-builder,market-builder
param(
    [string[]]$Agents = @("kobi-builder", "market-builder"),
    [string]$WorktreeRoot = "$env:USERPROFILE\hf26-wt"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$env:GH_TOKEN = & "C:\Program Files\GitHub CLI\gh.exe" auth token
New-Item -ItemType Directory -Force $WorktreeRoot, "$repo\sessions" | Out-Null

$jobs = foreach ($agent in $Agents) {
    $branch = "agent/$agent"
    $dir = Join-Path $WorktreeRoot $agent
    if (Test-Path $dir) { git -C $repo worktree remove --force $dir }
    git -C $repo branch -f $branch main | Out-Null
    git -C $repo worktree add $dir $branch | Out-Null
    # vadesiz.db is git-ignored, so each worktree starts with its own fresh database
    Write-Host "[$agent] started in $dir on $branch"
    Start-Job -Name $agent -ArgumentList $agent, $dir, $repo -ScriptBlock {
        param($agent, $dir, $repo)
        Set-Location $dir
        $share = Join-Path $repo "sessions\02-$agent.md"
        copilot --agent $agent -p "Do your job now on this repository. Stay inside your file ownership." `
            --allow-all --model auto --share $share 2>&1 | Out-File -Encoding utf8 (Join-Path $repo "logs\agent-$agent.log")
    }
}

$jobs | Wait-Job | Out-Null
foreach ($agent in $Agents) {
    $last = git -C $repo log --oneline -3 "agent/$agent"
    Write-Host "[$agent] done:`n$($last -join "`n")"
}
