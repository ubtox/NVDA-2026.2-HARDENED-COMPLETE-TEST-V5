[CmdletBinding()]
param(
    [string]$RunId = '',
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Join-Path $repoRoot 'NVDA-2026.2-HARDENED-SOURCE-V5'
$logRoot = Join-Path $repoRoot 'LAB-LOCAL-OUTPUT'
$certificationPath = Join-Path $logRoot 'EVOLUTION-CI-CERTIFICATION.txt'
$workflowLogPath = Join-Path $logRoot 'EVOLUTION-WORKFLOW-COMPLETE.log'
$defaultMetricsPath = Join-Path $logRoot 'EVOLUTION-METRICS.json'
$metricsPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $defaultMetricsPath
} elseif ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
} else {
    Join-Path $repoRoot $OutputPath
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$metricsDirectory = Split-Path -Parent $metricsPath
if ($metricsDirectory) {
    New-Item -ItemType Directory -Force -Path $metricsDirectory | Out-Null
}

function Read-KeyValueFile {
    param([Parameter(Mandatory)][string]$Path)

    $result = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $result
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $index = $line.IndexOf('=')
        if ($index -le 0) {
            continue
        }
        $key = $line.Substring(0, $index).Trim()
        $value = $line.Substring($index + 1).Trim()
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            $result[$key] = $value
        }
    }
    return $result
}

function Get-UnitTestMetrics {
    $candidates = @(
        (Join-Path $sourceRoot 'testOutput\unit\unitTests.xml'),
        (Join-Path $sourceRoot 'testOutput\unit\results.xml')
    )
    $path = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $path) {
        return [ordered]@{
            present = $false
            path = $null
            suite_count = 0
            tests = $null
            failures = $null
            errors = $null
            skipped = $null
            time_seconds = $null
        }
    }

    [xml]$xml = Get-Content -LiteralPath $path -Raw
    $root = $xml.DocumentElement
    if ($null -eq $root) {
        throw "Unit test XML has no document element: $path"
    }

    $suites = if ($root.LocalName -eq 'testsuite') {
        @($root)
    } elseif ($root.LocalName -eq 'testsuites') {
        @($root.SelectNodes('testsuite'))
    } else {
        throw "Unsupported unit test XML root '$($root.LocalName)' in $path"
    }

    $totals = [ordered]@{
        tests = [int64]0
        failures = [int64]0
        errors = [int64]0
        skipped = [int64]0
        time_seconds = [double]0
    }
    foreach ($suite in $suites) {
        foreach ($key in @('tests', 'failures', 'errors', 'skipped')) {
            $value = $suite.GetAttribute($key)
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $totals[$key] += [int64]::Parse($value, [Globalization.CultureInfo]::InvariantCulture)
            }
        }
        $timeValue = $suite.GetAttribute('time')
        if (-not [string]::IsNullOrWhiteSpace($timeValue)) {
            $totals['time_seconds'] += [double]::Parse($timeValue, [Globalization.CultureInfo]::InvariantCulture)
        }
    }

    return [ordered]@{
        present = $true
        path = $path.Substring($repoRoot.Length).TrimStart('\')
        suite_count = [int64]$suites.Count
        tests = $totals['tests']
        failures = $totals['failures']
        errors = $totals['errors']
        skipped = $totals['skipped']
        time_seconds = [Math]::Round($totals['time_seconds'], 3)
    }
}

function Get-ArtifactMetrics {
    $files = @()
    foreach ($relativeRoot in @('output', 'dist')) {
        $path = Join-Path $sourceRoot $relativeRoot
        if (Test-Path -LiteralPath $path) {
            $files += Get-ChildItem -LiteralPath $path -File -Recurse -ErrorAction Stop
        }
    }
    $files = @($files | Sort-Object FullName -Unique)

    $installers = @()
    foreach ($file in ($files | Where-Object { $_.Extension -ieq '.exe' -and $_.Name -match '^nvda' })) {
        $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
        $installers += [ordered]@{
            path = $file.FullName.Substring($repoRoot.Length).TrimStart('\')
            bytes = [int64]$file.Length
            sha256 = $hash.Hash.ToLowerInvariant()
        }
    }

    $totalBytes = [int64]0
    foreach ($file in $files) {
        $totalBytes += [int64]$file.Length
    }

    return [ordered]@{
        file_count = $files.Count
        total_bytes = $totalBytes
        installers = $installers
    }
}

$cert = Read-KeyValueFile -Path $certificationPath
$now = [DateTime]::UtcNow
$startUtc = $null
$durationSeconds = $null
if ($cert.ContainsKey('started_utc')) {
    $parsed = [DateTime]::MinValue
    if ([DateTime]::TryParse(
        $cert['started_utc'],
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind,
        [ref]$parsed
    )) {
        $startUtc = $parsed.ToUniversalTime()
        $durationSeconds = [Math]::Round(($now - $startUtc).TotalSeconds, 3)
    }
}

$gitSha = if ($env:GITHUB_SHA) {
    $env:GITHUB_SHA
} else {
    (& git -C $repoRoot rev-parse HEAD).Trim()
}

$workflowLog = [ordered]@{
    present = Test-Path -LiteralPath $workflowLogPath -PathType Leaf
    bytes = $null
    lines = $null
}
if ($workflowLog.present) {
    $workflowLog.bytes = [int64](Get-Item -LiteralPath $workflowLogPath).Length
    $workflowLog.lines = [int64](@(Get-Content -LiteralPath $workflowLogPath).Count)
}

$report = [ordered]@{
    schema = 1
    generated_utc = $now.ToString('o')
    repository = if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } elseif ($cert.ContainsKey('repository')) { $cert['repository'] } else { $null }
    ref = if ($env:GITHUB_REF) { $env:GITHUB_REF } elseif ($cert.ContainsKey('ref')) { $cert['ref'] } else { $null }
    sha = $gitSha
    run_id = if ($RunId) { $RunId } elseif ($env:GITHUB_RUN_ID) { $env:GITHUB_RUN_ID } elseif ($cert.ContainsKey('run_id')) { $cert['run_id'] } else { $null }
    run_attempt = if ($env:GITHUB_RUN_ATTEMPT) { $env:GITHUB_RUN_ATTEMPT } elseif ($cert.ContainsKey('run_attempt')) { $cert['run_attempt'] } else { $null }
    validation = [ordered]@{
        started_utc = if ($null -ne $startUtc) { $startUtc.ToString('o') } else { $null }
        elapsed_seconds = $durationSeconds
        workflow_log = $workflowLog
    }
    runtime = [ordered]@{
        powershell = $PSVersionTable.PSVersion.ToString()
        os = [Environment]::OSVersion.VersionString
        processor_count = [Environment]::ProcessorCount
        is_64_bit_process = [Environment]::Is64BitProcess
        is_64_bit_os = [Environment]::Is64BitOperatingSystem
    }
    unit_tests = Get-UnitTestMetrics
    artifacts = Get-ArtifactMetrics
}

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $metricsPath -Encoding utf8
Write-Host "Evolution metrics: $metricsPath" -ForegroundColor Green
Get-Content -LiteralPath $metricsPath | Write-Host
