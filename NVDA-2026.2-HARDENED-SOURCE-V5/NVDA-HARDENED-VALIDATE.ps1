#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipSystemTests,
    [switch]$SkipPackaging,
    [switch]$ForceSystemTests,
    [string]$PackageVersion = '2026.2-hardened-test-v5'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = $PSScriptRoot
$ValidationRevision = 'NVDA-2026.2-HARDENED-V5-20260903-R1'
$QaRoot = Join-Path $Root 'validation-artifacts'
$Log = Join-Path $QaRoot 'NVDA-HARDENED-VALIDATION.log'
$Summary = Join-Path $QaRoot 'NVDA-HARDENED-VALIDATION-SUMMARY.txt'
New-Item -ItemType Directory -Path $QaRoot -Force | Out-Null
Remove-Item -LiteralPath $Log, $Summary -Force -ErrorAction SilentlyContinue

$results = New-Object 'System.Collections.Generic.List[string]'
$failed = $false

function Write-Result {
    param([string]$Name, [string]$Status, [string]$Details = '')
    $line = '{0,-32} {1,-5} {2}' -f $Name, $Status, $Details
    $results.Add($line)
    Write-Host $line
}

function Write-ValidationSummary {
    $results | Out-File -LiteralPath $Summary -Encoding utf8
    Write-Host "`n=== SUMMARY ==="
    $results | ForEach-Object { Write-Host $_ }
    Write-Host "`nLog: $Log"
    Write-Host "Summary: $Summary"
}

function Stop-CriticalValidation {
    param([string]$Message)
    Write-Host "`nCRITICAL: $Message" -ForegroundColor Red
    Write-ValidationSummary
    exit 1
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter()][string[]]$Arguments = @()
    )

    # NVDA/SCons/Robot and other native tools can write ordinary informational
    # output to stderr. PowerShell must not convert that text into a terminating
    # NativeCommandError. The process exit code is the source of truth.
    if ([IO.Path]::IsPathRooted($FilePath) -or $FilePath.Contains('\') -or $FilePath.Contains('/')) {
        if (-not (Test-Path -LiteralPath $FilePath)) {
            throw "Native command not found: $FilePath"
        }
    }
    elseif (-not (Get-Command $FilePath -ErrorAction SilentlyContinue)) {
        throw "Native command not found: $FilePath"
    }

    $oldEap = $ErrorActionPreference
    $nativePrefVar = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
    if ($null -ne $nativePrefVar) {
        $oldNativePref = $PSNativeCommandUseErrorActionPreference
    }

    try {
        $ErrorActionPreference = 'Continue'
        if ($null -ne $nativePrefVar) {
            $PSNativeCommandUseErrorActionPreference = $false
        }

        $global:LASTEXITCODE = 0
        & $FilePath @Arguments 2>&1 | ForEach-Object {
            $text = $_.ToString()
            Write-Host $text
            $text | Out-File -LiteralPath $Log -Append -Encoding utf8
        }
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldEap
        if ($null -ne $nativePrefVar) {
            $PSNativeCommandUseErrorActionPreference = $oldNativePref
        }
    }

    if ($null -eq $code) { $code = 0 }
    if ($code -ne 0) {
        throw "$FilePath failed with exit code $code"
    }
}

function Invoke-Step {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][scriptblock]$Action,
        [switch]$Critical
    )

    Write-Host "`n=== $Name ==="
    try {
        & $Action
        Write-Result $Name 'PASS'
        return $true
    }
    catch {
        $script:failed = $true
        $message = $_.Exception.Message
        Write-Result $Name 'FAIL' $message
        "[$Name] $($_ | Out-String)" | Out-File -LiteralPath $Log -Append -Encoding utf8
        if ($Critical) {
            Stop-CriticalValidation "$Name failed: $message"
        }
        return $false
    }
}


function Invoke-ArchiveSafeUnitTests {
    # The official markdownTranslate round-trip test uses `git log` and
    # `git rev-parse` to embed a GitHub raw URL. GitHub source ZIPs intentionally
    # contain no top-level .git directory, so the upstream test cannot run from
    # an extracted archive without a repository context. Create a minimal,
    # temporary Git context containing only the Markdown fixtures required by
    # that test, run the complete upstream unit-test suite, then remove it.
    # No production source file is modified and no synthetic .git is packaged.
    $topLevelGit = Join-Path $Root '.git'
    $createdTemporaryGit = $false

    try {
        if (-not (Test-Path -LiteralPath $topLevelGit)) {
            Write-Host '[INFO] No top-level .git directory: creating temporary archive-safe unit-test Git context.'
            Invoke-NativeChecked 'git.exe' @('-C', $Root, 'init', '--quiet')
            $createdTemporaryGit = $true
            Invoke-NativeChecked 'git.exe' @('-C', $Root, 'config', 'user.name', 'NVDA Hardened Validation')
            Invoke-NativeChecked 'git.exe' @('-C', $Root, 'config', 'user.email', 'nvda-hardened-validation@invalid.local')
            Invoke-NativeChecked 'git.exe' @('-C', $Root, 'config', 'commit.gpgSign', 'false')
            Invoke-NativeChecked 'git.exe' @('-C', $Root, 'config', 'core.hooksPath', 'NUL')
            Invoke-NativeChecked 'git.exe' @('-C', $Root, 'add', '-f', '--', 'tests/markdownTranslate')
            Invoke-NativeChecked 'git.exe' @(
                '-C', $Root, 'commit', '--quiet', '--no-gpg-sign',
                '-m', 'Temporary archive validation context for markdownTranslate tests'
            )
        }
        else {
            $repoRoot = (& git.exe -C $Root rev-parse --show-toplevel 2>$null)
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
                throw 'Top-level .git exists but is not a valid Git repository.'
            }
            $expectedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
            $actualRoot = [IO.Path]::GetFullPath($repoRoot.Trim()).TrimEnd('\')
            if (-not $actualRoot.Equals($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Unexpected Git repository root: $actualRoot"
            }
            Write-Host "[OK] Existing Git repository context: $actualRoot"
        }

        Invoke-NativeChecked (Join-Path $Root 'rununittests.bat')
    }
    finally {
        if ($createdTemporaryGit -and (Test-Path -LiteralPath $topLevelGit)) {
            Remove-Item -LiteralPath $topLevelGit -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $topLevelGit) {
                throw 'Unable to remove temporary archive-safe .git directory after unit tests.'
            }
            Write-Host '[OK] Temporary archive-safe unit-test Git context removed.'
        }
    }
}

function Resolve-ChromeExecutable {
    $cmd = Get-Command 'chrome.exe' -ErrorAction SilentlyContinue
    if ($null -ne $cmd -and -not [string]::IsNullOrWhiteSpace($cmd.Source)) {
        return $cmd.Source
    }

    $candidates = New-Object 'System.Collections.Generic.List[string]'
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe'))
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'))
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if (-not [string]::IsNullOrWhiteSpace($programFilesX86)) {
        $candidates.Add((Join-Path $programFilesX86 'Google\Chrome\Application\chrome.exe'))
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Resolve-VSCodeExecutable {
    $commands = @('code.cmd', 'code.exe')
    foreach ($name in $commands) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $cmd -and -not [string]::IsNullOrWhiteSpace($cmd.Source)) {
            return $cmd.Source
        }
    }

    $candidates = New-Object 'System.Collections.Generic.List[string]'
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\Code.exe'))
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles 'Microsoft VS Code\Code.exe'))
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if (-not [string]::IsNullOrWhiteSpace($programFilesX86)) {
        $candidates.Add((Join-Path $programFilesX86 'Microsoft VS Code\Code.exe'))
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Assert-SystemTestPreflight {
    if (-not [Environment]::UserInteractive) {
        throw 'Robot system tests require an interactive Windows desktop session.'
    }

    $chromePath = Resolve-ChromeExecutable
    if ([string]::IsNullOrWhiteSpace($chromePath)) {
        throw 'Google Chrome is required for NVDA Robot system tests, but chrome.exe was not found.'
    }
    $script:SystemChromePath = $chromePath

    $vsCodePath = Resolve-VSCodeExecutable
    if ([string]::IsNullOrWhiteSpace($vsCodePath)) {
        throw 'Visual Studio Code is required by the NVDA Robot vscodeTests suite, but no VS Code launcher was found.'
    }

    $chromeDir = Split-Path -Parent $chromePath
    $pathEntries = @($env:PATH -split ';')
    if (-not ($pathEntries | Where-Object { $_.TrimEnd('\').Equals($chromeDir.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) })) {
        $env:PATH = "$chromeDir;$env:PATH"
    }

    # Robot tests deliberately take control of focus, keyboard input, Chrome,
    # Notepad, VS Code and NVDA itself. A simultaneously running screen reader
    # or an already-open test application makes speech assertions unreliable.
    $conflictNames = @('nvda', 'jfw', 'Narrator', 'chrome', 'Code', 'notepad', 'ChatGPT')
    $conflicts = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $conflictNames -contains $_.ProcessName
    })
    if ($conflicts.Count -gt 0) {
        $conflictText = (($conflicts | Select-Object -ExpandProperty ProcessName -Unique | Sort-Object) -join ', ')
        if (-not $ForceSystemTests) {
            throw "System-test desktop is not isolated. Close these processes first: $conflictText. Run in a dedicated Windows session/VM, or use -SkipSystemTests. -ForceSystemTests overrides this protection but can produce false failures."
        }
        Write-Host "[WARN] -ForceSystemTests: continuing despite conflicting processes: $conflictText" -ForegroundColor Yellow
    }

    $portConflict = @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq 8270 })
    if ($portConflict.Count -gt 0 -and -not $ForceSystemTests) {
        throw 'TCP port 8270 (NVDA Robot spy) is already in use. Close the stale NVDA/Robot test process before continuing.'
    }

    $staleProfile = Join-Path ([IO.Path]::GetTempPath()) 'nvdaProfile'
    if (Test-Path -LiteralPath $staleProfile) {
        Remove-Item -LiteralPath $staleProfile -Recurse -Force -ErrorAction Stop
        Write-Host "[OK] Removed stale Robot profile: $staleProfile"
    }

    Write-Host "[OK] Chrome: $chromePath"
    Write-Host "[OK] Visual Studio Code: $vsCodePath"
    Write-Host '[OK] Robot spy port 8270 is available.'
    Write-Host '[IMPORTANT] Do not use the keyboard or mouse while Robot system tests are running.' -ForegroundColor Yellow
}

function Invoke-HardenedSystemTests {
    # NV Access CI deliberately warms Chrome using the same arguments as the
    # Robot tests because the first browser start can be flaky after updates.
    $chromeArgs = @(
        '--no-first-run',
        '--force-renderer-accessibility',
        '--ash-no-nudges',
        '--browser-test',
        '--disable-default-apps',
        '--keep-alive-for-test',
        '--suppress-message-center-popups',
        '--disable-notifications',
        '--no-experiments',
        '--no-default-browser-check',
        '--lang=en-US',
        '--disable-session-crashed-bubble'
    )

    $preExistingChromePids = @(Get-Process chrome -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    try {
        Start-Process -FilePath $script:SystemChromePath -ArgumentList $chromeArgs -WindowStyle Minimized | Out-Null
        Start-Sleep -Seconds 3
        Invoke-NativeChecked (Join-Path $Root 'runsystemtests.bat') @('--include', 'NVDA')
    }
    finally {
        # Preflight normally guarantees no pre-existing Chrome. If force mode
        # was used, preserve processes that existed before this validation run.
        $testChrome = @(Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {
            $preExistingChromePids -notcontains $_.Id
        })
        if ($testChrome.Count -gt 0) {
            $testChrome | Stop-Process -Force -ErrorAction SilentlyContinue
        }
    }
}

function Assert-PathExists {
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [ValidateSet('Any', 'File', 'Directory')][string]$Type = 'Any'
    )
    $path = Join-Path $Root $RelativePath
    $ok = switch ($Type) {
        'File' { Test-Path -LiteralPath $path -PathType Leaf }
        'Directory' { Test-Path -LiteralPath $path -PathType Container }
        default { Test-Path -LiteralPath $path }
    }
    if (-not $ok) {
        throw "Required generated path is missing: $RelativePath"
    }
    Write-Host "[OK] $RelativePath"
}

Set-Location $Root
"NVDA hardened validation V5 - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')" | Out-File -LiteralPath $Log -Encoding utf8
"Revision: $ValidationRevision" | Out-File -LiteralPath $Log -Append -Encoding utf8
"Root: $Root" | Out-File -LiteralPath $Log -Append -Encoding utf8
Write-Host "NVDA hardened validation V5"
Write-Host "Revision: $ValidationRevision"

$ensureUv = Join-Path $Root 'ensureuv.ps1'
$manifestPath = Join-Path $Root 'NVDA-HARDENED-SUBMODULES.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Stop-CriticalValidation 'NVDA-HARDENED-SUBMODULES.json is missing.'
}
$submoduleManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

# Refuse to validate a stale/mixed extracted tree with a newer validator.
Invoke-Step -Name 'Archive revision' -Critical -Action {
    $revisionPath = Join-Path $Root 'NVDA-HARDENED-REVISION.txt'
    if (-not (Test-Path -LiteralPath $revisionPath -PathType Leaf)) {
        throw 'NVDA-HARDENED-REVISION.txt is missing. Extract V5 into a new directory.'
    }
    $archiveRevision = (Get-Content -LiteralPath $revisionPath -Raw).Trim()
    if ($archiveRevision -ne $ValidationRevision) {
        throw "Archive/validator revision mismatch. Expected $ValidationRevision, got $archiveRevision"
    }
    Write-Host "[OK] Archive revision: $archiveRevision"
} | Out-Null

# Critical phase 1: exact pinned source dependencies are verified. If this
# archive was freshly extracted and submodule folders are empty, prepare them
# automatically from the pinned manifest before continuing.
Invoke-Step -Name 'Pinned source dependencies' -Critical -Action {
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        throw 'Git for Windows is required.'
    }

    $needsPrepare = $false
    foreach ($dep in $submoduleManifest.submodules) {
        $path = Join-Path $Root (([string]$dep.path) -replace '/', [IO.Path]::DirectorySeparatorChar)
        $gitDir = Join-Path $path '.git'
        if (-not (Test-Path -LiteralPath $gitDir)) {
            $needsPrepare = $true
            break
        }
        $actual = (& git -C $path rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne [string]$dep.commit) {
            $needsPrepare = $true
            break
        }
    }

    if ($needsPrepare) {
        Write-Host 'Pinned dependencies are incomplete or mismatched; preparing them now.'
        Invoke-NativeChecked 'powershell.exe' @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            (Join-Path $Root 'NVDA-HARDENED-PREPARE-SOURCE.ps1')
        )
    }

    foreach ($dep in $submoduleManifest.submodules) {
        $path = Join-Path $Root (([string]$dep.path) -replace '/', [IO.Path]::DirectorySeparatorChar)
        $gitDir = Join-Path $path '.git'
        if (-not (Test-Path -LiteralPath $gitDir)) {
            throw "$($dep.path) is still missing after source preparation."
        }
        $actual = (& git -C $path rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne [string]$dep.commit) {
            throw "$($dep.path) SHA mismatch. Expected $($dep.commit), got $actual"
        }
    }
} | Out-Null

# Critical phase 2: create the exact frozen Python environment first.
Invoke-Step -Name 'Dependencies' -Critical -Action {
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'sync', '--frozen',
        '--group', 'dev',
        '--group', 'unit-tests',
        '--group', 'system-tests',
        '--group', 'lint',
        '--group', 'license-check'
    )
} | Out-Null

# Critical phase 3: SCons must populate source/louis and generate COM bindings
# before Pyright or any tests that import the NVDA source tree are allowed to run.
Invoke-Step -Name 'Prepare generated source' -Critical -Action {
    Invoke-NativeChecked (Join-Path $Root 'scons.bat') @('--all-cores', 'source')
} | Out-Null

Invoke-Step -Name 'Generated source readiness' -Critical -Action {
    Assert-PathExists 'source\louis' 'Directory'
    Assert-PathExists 'source\comInterfaces\Accessibility.py' 'File'
    Assert-PathExists 'source\comInterfaces\IAccessible2Lib.py' 'File'
    Assert-PathExists 'source\comInterfaces\tom.py' 'File'
    Assert-PathExists 'source\comInterfaces\UIAutomationClient.py' 'File'
    Assert-PathExists 'source\comInterfaces\SpeechLib.py' 'File'
} | Out-Null

# These checks now run only after generated source is complete.
Invoke-Step 'Custom speech regression' {
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'run', '--directory', $Root, 'python', 'tests\zeroRegression_speakTypedCharacters.pyqa'
    )
} | Out-Null

Invoke-Step 'Custom braille audit' {
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'run', '--directory', $Root, 'python', 'tests\zeroRegression_brailleSymbols.pyqa'
    )
} | Out-Null

Invoke-Step 'Custom add-on cleanup regression' {
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'run', '--directory', $Root, 'python', 'tests\zeroRegression_addonCleanup.pyqa'
    )
} | Out-Null

Invoke-Step 'Custom x86 synth runtime regression' {
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'run', '--directory', $Root, 'python', 'tests\zeroRegression_synthDriverHost32Runtime.pyqa'
    )
} | Out-Null

Invoke-Step 'Ruff check' {
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'run', '--group', 'lint', '--directory', $Root, 'ruff', 'check', '.'
    )
} | Out-Null

Invoke-Step 'Ruff format check' {
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'run', '--group', 'lint', '--directory', $Root, 'ruff', 'format', '--check', '.'
    )
} | Out-Null

Invoke-Step 'Pyright' {
    # Keep the repository-pinned Pyright version from uv.lock. The update
    # notification printed by Pyright is informational and is not a failure.
    Invoke-NativeChecked 'powershell.exe' @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ensureUv,
        'run', '--group', 'lint', '--directory', $Root, 'pyright'
    )
} | Out-Null

Invoke-Step 'Unit tests' {
    Invoke-ArchiveSafeUnitTests
} | Out-Null

if (-not $SkipSystemTests) {
    $systemPreflightOk = Invoke-Step 'System test preflight' {
        Assert-SystemTestPreflight
    }
    if ($systemPreflightOk) {
        Invoke-Step 'System tests' {
            Invoke-HardenedSystemTests
        } | Out-Null
    }
    else {
        Write-Result 'System tests' 'SKIP' 'System-test preflight failed; no Robot tests were executed'
    }
}
else {
    Write-Result 'System test preflight' 'SKIP' 'Requested by -SkipSystemTests'
    Write-Result 'System tests' 'SKIP' 'Requested by -SkipSystemTests'
}

Invoke-Step 'Translator comments POT' {
    Invoke-NativeChecked (Join-Path $Root 'runcheckpot.bat')
} | Out-Null

Invoke-Step 'Dependency licenses' {
    Invoke-NativeChecked (Join-Path $Root 'runlicensecheck.bat')
} | Out-Null

if ($failed) {
    Write-Result 'Build dist' 'SKIP' 'Earlier validation step failed'
    Write-Result 'Build launcher' 'SKIP' 'Earlier validation step failed'
}
elseif ($SkipPackaging) {
    Write-Result 'Build dist' 'SKIP' 'Requested by -SkipPackaging'
    Write-Result 'Build launcher' 'SKIP' 'Requested by -SkipPackaging'
}
else {
    Invoke-Step 'Build dist' {
        Invoke-NativeChecked (Join-Path $Root 'scons.bat') @('--all-cores', 'dist', "version=$PackageVersion")
    } | Out-Null
    Invoke-Step 'Build launcher' {
        Invoke-NativeChecked (Join-Path $Root 'scons.bat') @('--all-cores', 'launcher', "version=$PackageVersion")
    } | Out-Null
}

Write-ValidationSummary
if ($failed) { exit 1 }
exit 0
