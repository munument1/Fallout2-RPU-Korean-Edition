# Run ONLY candidate comparison, never auto-edit a game file or publish a release.
# Uses one Windows Task Scheduler session at a time. Checkpoints are persisted.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "korean-contextual-review"
New-Item -Path $out -ItemType Directory -Force | Out-Null
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$lockPath = Join-Path $out "scheduled-worker.lock"
try {
    $lock = [System.IO.File]::Open(
        $lockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
} catch [System.IO.IOException] {
    Write-Output "Another scheduled contextual review run is already active."
    exit 0
}
try {
    Set-Location -LiteralPath $root
    $log = Join-Path $out ("review-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")
    $ollama = Get-Command ollama -ErrorAction Stop
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 8 | Out-Null
    } catch {
        Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 7
    }
    $installed = (& $ollama.Source list | Out-String)
    if (($installed -notmatch "Hy-MT2-7B-GGUF") -or ($installed -notmatch "translategemma:12b")) {
        "Local translation models missing; no paid API or model downloads started." |
            Out-File -FilePath $log -Encoding UTF8
        exit 2
    }
    $python = (Get-Command python -ErrorAction Stop).Source
    # Limited nightly run, not indefinite GPU usage. Completed IDs skipped.
    $maxItems = if ($env:RPU_CONTEXT_MAX_ITEMS) { [int]$env:RPU_CONTEXT_MAX_ITEMS } else { 5000 }
    $maxMinutes = if ($env:RPU_CONTEXT_MAX_MINUTES) { [double]$env:RPU_CONTEXT_MAX_MINUTES } else { 115 }
    & $python "korean/contextual_review_queue.py" --model both --out "korean-contextual-review" --max-items $maxItems --max-minutes $maxMinutes --timeout 150 *> $log
    $rc = $LASTEXITCODE
    if ($rc -ne 0) {
        Write-Output "Contextual review stopped with exit code $rc. Log: $log"
    }
    exit $rc
}
finally {
    $lock.Dispose()
}
