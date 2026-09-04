[CmdletBinding()]
param(
    [ValidateSet('Source','Dist','Launcher','All')]
    [string]$Mode = 'Source',
    [switch]$Parallel
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Join-Path $repoRoot 'NVDA-2026.2-HARDENED-SOURCE-V5'

if (-not (Test-Path -LiteralPath $sourceRoot)) {
    throw "NVDA source tree not found: $sourceRoot"
}

Set-Location $sourceRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [scriptblock]$Command
    )
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked 'Git submodules' { git submodule update --init --recursive }
Invoke-Checked 'Locked dependency sync' { uv sync --locked }

Write-Host "`n=== Python runtime ===" -ForegroundColor Cyan
$py = uv run python -c "import platform,struct,sys; print(sys.version); print(platform.machine()); print(struct.calcsize('P')*8)"
if ($LASTEXITCODE -ne 0) { throw 'Python runtime verification failed' }
$py | ForEach-Object { Write-Host $_ }

Invoke-Checked 'Ruff' { uv run ruff check source tests }
Invoke-Checked 'Ruff format check' { uv run ruff format --check source tests }

$parallelArgs = @()
if ($Parallel) {
    $parallelArgs = @('--all-cores')
} else {
    $parallelArgs = @('-j','1')
}

function Invoke-SConsTarget([string]$Target) {
    Invoke-Checked "SCons $Target" {
        uv run scons $Target @parallelArgs
    }
}

switch ($Mode) {
    'Source'   { Invoke-SConsTarget 'source' }
    'Dist'     { Invoke-SConsTarget 'source'; Invoke-SConsTarget 'dist' }
    'Launcher' { Invoke-SConsTarget 'source'; Invoke-SConsTarget 'launcher' }
    'All'      {
        Invoke-SConsTarget 'source'
        Invoke-SConsTarget 'dist'
        Invoke-SConsTarget 'launcher'
    }
}

Write-Host "`nLAB BUILD PASS ($Mode)" -ForegroundColor Green
Write-Host "Source: $sourceRoot" -ForegroundColor Green
