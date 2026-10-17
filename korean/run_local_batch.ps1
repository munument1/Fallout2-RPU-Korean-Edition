# The review works on the user's PC only (no paid API calls).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = "1"
$out = Join-Path $root "korean-auto-review"
New-Item -Path $out -ItemType Directory -Force | Out-Null
$lockPath = Join-Path $out "worker.lock"
try {
    $lock = [System.IO.File]::Open(
        $lockPath, [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None
    )
} catch [System.IO.IOException] {
    Write-Output "An automatic review run is already active."
    exit 0
}
try {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $log = Join-Path $out ("review-" + $stamp + ".txt")
    Set-Location -LiteralPath $root
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        "ERROR: Ollama not installed or not on PATH." | Out-File -FilePath $log -Encoding UTF8
        exit 2
    }
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 | Out-Null
    } catch {
        Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 5
    }
    $python = (Get-Command python -ErrorAction Stop).Source
    $maxMinutes = if ($env:RPU_REVIEW_MAX_MINUTES) { [double]$env:RPU_REVIEW_MAX_MINUTES } else { 115 }
    $maxChunks = if ($env:RPU_REVIEW_MAX_CHUNKS) { [int]$env:RPU_REVIEW_MAX_CHUNKS } else { 0 }
    & $python "korean/auto_review_queue.py" --model "qwen3:14b" --out "korean-auto-review" --chunk-size 6 --max-minutes $maxMinutes --max-chunks $maxChunks --timeout-seconds 240 *> $log
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        "ERROR: Auto review returned $exitCode. See $log" | Write-Output
    }
    exit $exitCode
}
finally {
    $lock.Dispose()
}
