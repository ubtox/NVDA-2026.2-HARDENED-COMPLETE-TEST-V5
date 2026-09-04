[CmdletBinding()]
param(
    [ValidateSet('Source','Dist','Launcher','All')]
    [string]$Mode = 'Source',
    [switch]$Parallel,
    [switch]$SkipQuality,
    [switch]$SkipUnitTests
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Join-Path $repoRoot 'NVDA-2026.2-HARDENED-SOURCE-V5'
$logRoot = Join-Path $repoRoot 'LAB-LOCAL-OUTPUT'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$buildLog = Join-Path $logRoot "LAB-BUILD-$stamp.log"
$hashFile = Join-Path $logRoot "LAB-ARTIFACT-SHA256-$stamp.txt"

if (-not (Test-Path -LiteralPath $sourceRoot)) {
    throw "NVDA source tree not found: $sourceRoot"
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
Set-Location $sourceRoot

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [scriptblock]$Command
    )
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Command
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "$Name failed with exit code $code"
    }
}

function Invoke-SConsTarget {
    param([Parameter(Mandatory)][string]$Target)

    $args = @($Target)
    if ($Parallel) {
        $args += '--all-cores'
    } else {
        $args += @('-j', '1')
    }

    Write-Host "`n=== SCons $Target ===" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & uv run scons @args 2>&1 | Tee-Object -FilePath $buildLog -Append
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "SCons $Target failed with exit code $code"
    }
    if (-not (Select-String -LiteralPath $buildLog -SimpleMatch 'scons: done building targets.' -Quiet)) {
        throw "SCons $Target returned success but the final completion marker was not found"
    }
}

Write-Host "NVDA 2026.2 LAB" -ForegroundColor Green
Write-Host "Repository: $repoRoot"
Write-Host "Source:     $sourceRoot"
Write-Host "Mode:       $Mode"
Write-Host "Parallel:   $Parallel"

Invoke-NativeChecked 'Git integrity (diff --check)' { git diff --check }
Invoke-NativeChecked 'uv lock verification' { uv lock --check }
Invoke-NativeChecked 'Locked dependency sync' { uv sync --locked }

Write-Host "`n=== Python runtime ===" -ForegroundColor Cyan
$global:LASTEXITCODE = 0
$pythonInfoJson = & uv run python -c "import json,platform,struct,sys; print(json.dumps({'version':platform.python_version(),'machine':platform.machine(),'bits':struct.calcsize('P')*8,'executable':sys.executable}))"
if ($LASTEXITCODE -ne 0) {
    throw 'Python runtime verification failed'
}
$pythonInfo = $pythonInfoJson | ConvertFrom-Json
$pythonInfo | Format-List | Out-Host
if ($pythonInfo.version -ne '3.13.13') {
    throw "Expected CPython 3.13.13, got $($pythonInfo.version)"
}
if ([int]$pythonInfo.bits -ne 64) {
    throw "Expected a 64-bit Python runtime, got $($pythonInfo.bits)-bit"
}
if ($pythonInfo.machine -notmatch 'AMD64|x86_64') {
    throw "Expected AMD64/x86_64 Python, got $($pythonInfo.machine)"
}

Invoke-NativeChecked 'Python compileall' { uv run python -m compileall -q source tests\unit }

# Generate the source-side artifacts (comInterfaces, louis bindings, etc.) before type checking.
Invoke-SConsTarget 'source'

if (-not $SkipQuality) {
    Invoke-NativeChecked 'Ruff check' { uv run --group lint ruff check . }
    Invoke-NativeChecked 'Ruff format check' { uv run --group lint ruff format --check . }
    Invoke-NativeChecked 'Pyright' { uv run --group lint pyright }
}

if (-not $SkipUnitTests) {
    Invoke-NativeChecked 'NVDA unit tests' { .\rununittests.bat }
}

switch ($Mode) {
    'Source' { }
    'Dist' { Invoke-SConsTarget 'dist' }
    'Launcher' { Invoke-SConsTarget 'launcher' }
    'All' {
        Invoke-SConsTarget 'dist'
        Invoke-SConsTarget 'launcher'
    }
}

Write-Host "`n=== Artifact SHA-256 ===" -ForegroundColor Cyan
$artifactCandidates = @()
foreach ($candidate in @('output', 'dist')) {
    $path = Join-Path $sourceRoot $candidate
    if (Test-Path -LiteralPath $path) {
        $artifactCandidates += Get-ChildItem -LiteralPath $path -File -Recurse -ErrorAction Stop
    }
}
$artifactCandidates = @($artifactCandidates | Sort-Object FullName -Unique)
if ($artifactCandidates.Count -gt 0) {
    $artifactCandidates |
        Get-FileHash -Algorithm SHA256 |
        ForEach-Object {
            $relative = $_.Path.Substring($sourceRoot.Length).TrimStart('\')
            "$($_.Hash) *$relative"
        } |
        Set-Content -LiteralPath $hashFile -Encoding ASCII
    Write-Host "Hashes: $hashFile"
} else {
    Write-Host 'No dist/output artifacts produced in this mode.'
}

Invoke-NativeChecked 'Final Git integrity (diff --check)' { git diff --check }

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " NVDA 2026.2 LAB VALIDATION PASS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Mode:      $Mode"
Write-Host "Build log: $buildLog"
if (Test-Path -LiteralPath $hashFile) {
    Write-Host "SHA-256:   $hashFile"
}
