#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$ForceRefresh
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = $PSScriptRoot
$ManifestPath = Join-Path $Root 'NVDA-HARDENED-SUBMODULES.json'
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json

function Invoke-GitChecked {
    param(
        [Parameter(Mandatory)][string[]]$Arguments
    )
    & git @Arguments
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    if ($code -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $code"
    }
}

function Test-DirectoryHasContent {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    return $null -ne (Get-ChildItem -LiteralPath $Path -Force | Select-Object -First 1)
}

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    throw 'Git for Windows is required. Install Git, reopen PowerShell, then rerun this script.'
}

Write-Host "NVDA baseline tag: $($Manifest.baseline.tag)"
Write-Host "NVDA baseline commit: $($Manifest.baseline.commit)"
Write-Host "Preparing $($Manifest.submodules.Count) pinned submodules..."

foreach ($dep in $Manifest.submodules) {
    $relativePath = [string]$dep.path
    $repo = [string]$dep.repository
    $sha = [string]$dep.commit
    $path = Join-Path $Root ($relativePath -replace '/', [IO.Path]::DirectorySeparatorChar)

    Write-Host "`n=== $relativePath ==="
    Write-Host "Repository: $repo"
    Write-Host "Pinned SHA: $sha"

    $gitDir = Join-Path $path '.git'
    if ($ForceRefresh -and (Test-Path -LiteralPath $path)) {
        Write-Host 'Removing existing dependency because -ForceRefresh was requested.'
        Remove-Item -LiteralPath $path -Recurse -Force
    }

    if (Test-Path -LiteralPath $gitDir) {
        $current = (& git -C $path rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Could not read HEAD for $relativePath"
        }
        if ($current -ne $sha) {
            Write-Host "Current SHA differs ($current). Fetching pinned SHA..."
            Invoke-GitChecked -Arguments @('-C', $path, 'fetch', '--depth', '1', 'origin', $sha)
            Invoke-GitChecked -Arguments @('-C', $path, 'checkout', '--detach', $sha)
        }
        else {
            Write-Host 'Pinned SHA already checked out.'
        }
        Invoke-GitChecked -Arguments @('-C', $path, 'submodule', 'sync', '--recursive')
        Invoke-GitChecked -Arguments @('-C', $path, 'submodule', 'update', '--init', '--recursive')
        continue
    }

    if (Test-DirectoryHasContent -Path $path) {
        throw "$relativePath is not empty and is not a Git checkout. Move/remove it or rerun with -ForceRefresh."
    }

    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $path -Force | Out-Null

    Invoke-GitChecked -Arguments @('-C', $path, 'init')
    Invoke-GitChecked -Arguments @('-C', $path, 'remote', 'add', 'origin', $repo)
    try {
        Invoke-GitChecked -Arguments @('-C', $path, 'fetch', '--depth', '1', 'origin', $sha)
        Invoke-GitChecked -Arguments @('-C', $path, 'checkout', '--detach', 'FETCH_HEAD')
    }
    catch {
        Write-Warning 'Direct shallow fetch by SHA failed. Falling back to a normal clone/fetch.'
        Remove-Item -LiteralPath $path -Recurse -Force
        Invoke-GitChecked -Arguments @('clone', '--no-checkout', $repo, $path)
        Invoke-GitChecked -Arguments @('-C', $path, 'checkout', '--detach', $sha)
    }

    $checkedOut = (& git -C $path rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $checkedOut -ne $sha) {
        throw "Pinned SHA verification failed for $relativePath. Expected $sha, got $checkedOut"
    }

    Invoke-GitChecked -Arguments @('-C', $path, 'submodule', 'sync', '--recursive')
    Invoke-GitChecked -Arguments @('-C', $path, 'submodule', 'update', '--init', '--recursive')
    Write-Host "OK: $relativePath @ $checkedOut"
}

Write-Host "`n=== VERIFY ALL PINNED DEPENDENCIES ==="
$errors = @()
foreach ($dep in $Manifest.submodules) {
    $path = Join-Path $Root (([string]$dep.path) -replace '/', [IO.Path]::DirectorySeparatorChar)
    $expected = [string]$dep.commit
    if (-not (Test-Path -LiteralPath (Join-Path $path '.git'))) {
        $errors += "$($dep.path): missing Git checkout"
        continue
    }
    $actual = (& git -C $path rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $actual -ne $expected) {
        $errors += "$($dep.path): expected $expected, got $actual"
    }
}

if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_ }
    throw 'One or more pinned dependencies failed verification.'
}

Write-Host 'All pinned NVDA 2026.2 dependencies are ready.' -ForegroundColor Green
