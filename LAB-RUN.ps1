[CmdletBinding()]
param(
    [string[]]$NvdaArgs = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Join-Path $repoRoot 'NVDA-2026.2-HARDENED-SOURCE-V5'
$runner = Join-Path $sourceRoot 'runnvda.bat'

if (-not (Test-Path -LiteralPath $runner)) {
    throw "NVDA runner not found: $runner"
}

Set-Location $sourceRoot
& $runner @NvdaArgs
exit $LASTEXITCODE
