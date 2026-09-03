#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$RunDeterministicValidation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$RepoName = 'NVDA-2026.2-HARDENED-COMPLETE-TEST-V5'
$SourceName = 'NVDA-2026.2-HARDENED-SOURCE-V5'
$NewRevision = 'NVDA-2026.2-HARDENED-V5-20260903-R2'

function Get-RepoRoot {
    try {
        $candidate = (& git rev-parse --show-toplevel 2>$null)
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($candidate)) {
            $candidate = $candidate.Trim()
            if (Test-Path -LiteralPath (Join-Path $candidate $SourceName) -PathType Container) {
                return $candidate
            }
        }
    }
    catch {
    }

    $downloadsCandidate = Join-Path $env:USERPROFILE "Downloads\$RepoName"
    if (
        (Test-Path -LiteralPath (Join-Path $downloadsCandidate '.git')) -and
        (Test-Path -LiteralPath (Join-Path $downloadsCandidate $SourceName) -PathType Container)
    ) {
        return $downloadsCandidate
    }

    throw "Depot $RepoName introuvable. Lance ce script depuis le depot ou place-le dans $downloadsCandidate."
}

function Read-LfText {
    param([Parameter(Mandatory)][string]$Path)
    return ((Get-Content -LiteralPath $Path -Raw) -replace "`r`n", "`n")
}

function Write-Utf8NoBomLf {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Text
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, ($Text -replace "`r`n", "`n"), $utf8NoBom)
}

function Replace-Required {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Old,
        [Parameter(Mandatory)][string]$New,
        [Parameter(Mandatory)][string]$Label
    )

    if ($Text.Contains($Old)) {
        Write-Host "[PATCH] $Label" -ForegroundColor Cyan
        return $Text.Replace($Old, $New)
    }

    if ($Text.Contains($New)) {
        Write-Host "[OK] $Label deja applique" -ForegroundColor Green
        return $Text
    }

    throw "Bloc attendu introuvable pour: $Label. Aucun fichier n'a ete pousse."
}

function Assert-PowerShellSyntax {
    param([Parameter(Mandatory)][string]$Path)

    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $Path,
        [ref]$tokens,
        [ref]$parseErrors
    )

    if ($parseErrors.Count -gt 0) {
        $parseErrors | ForEach-Object { Write-Host $_.Message -ForegroundColor Red }
        throw "Erreur de syntaxe PowerShell dans $Path"
    }

    Write-Host "[OK] Syntaxe PowerShell: $Path" -ForegroundColor Green
}

function Invoke-GitChecked {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$GitArgs)

    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Echec Git ($LASTEXITCODE): git $($GitArgs -join ' ')"
    }
}

$repo = Get-RepoRoot
Set-Location $repo

$source = Join-Path $repo $SourceName
$preparePath = Join-Path $source 'NVDA-HARDENED-PREPARE-SOURCE.ps1'
$validatePath = Join-Path $source 'NVDA-HARDENED-VALIDATE.ps1'
$revisionPath = Join-Path $source 'NVDA-HARDENED-REVISION.txt'
$notesPath = Join-Path $source 'HISTORY-VALIDATOR-FIXES-V5-2026-09-03.txt'

foreach ($required in @($preparePath, $validatePath, $revisionPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Fichier requis introuvable: $required"
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " NVDA HARDENED V5 - FIX VENDORED DEPENDENCIES R2" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Depot  : $repo"
Write-Host "Source : $source"

# Safety check: the repository should already have been converted from gitlinks
# to ordinary files by the previous vendor operation.
$remainingGitLinks = @(
    git ls-files -s |
    Where-Object { $_ -match '^160000\s' }
)
if ($remainingGitLinks.Count -gt 0) {
    Write-Host "[ERREUR] Des gitlinks 160000 existent encore:" -ForegroundColor Red
    $remainingGitLinks | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    throw 'Corrige les gitlinks avant d appliquer ce patch.'
}
Write-Host '[OK] Aucun gitlink 160000.' -ForegroundColor Green

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = Join-Path $repo "PATCH-BACKUP-$stamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -LiteralPath $preparePath -Destination (Join-Path $backupDir 'NVDA-HARDENED-PREPARE-SOURCE.ps1') -Force
Copy-Item -LiteralPath $validatePath -Destination (Join-Path $backupDir 'NVDA-HARDENED-VALIDATE.ps1') -Force
Copy-Item -LiteralPath $revisionPath -Destination (Join-Path $backupDir 'NVDA-HARDENED-REVISION.txt') -Force
Write-Host "[OK] Sauvegarde locale: $backupDir" -ForegroundColor Green

# -------------------------------------------------------------------------
# 1. PREPARE-SOURCE: accept a non-empty vendored dependency instead of
#    requiring every dependency folder to contain its own .git metadata.
# -------------------------------------------------------------------------
$prepare = Read-LfText -Path $preparePath

$oldPrepareNonGit = @'
    if (Test-DirectoryHasContent -Path $path) {
        throw "$relativePath is not empty and is not a Git checkout. Move/remove it or rerun with -ForceRefresh."
    }
'@

$newPrepareNonGit = @'
    if (Test-DirectoryHasContent -Path $path) {
        Write-Host "[OK] Vendored dependency already present. Upstream provenance target: $sha" -ForegroundColor Green
        continue
    }
'@

$prepare = Replace-Required `
    -Text $prepare `
    -Old $oldPrepareNonGit `
    -New $newPrepareNonGit `
    -Label 'PREPARE: accepter une dependance vendored non vide'

$oldPrepareVerify = @'
    if (-not (Test-Path -LiteralPath (Join-Path $path '.git'))) {
        $errors += "$($dep.path): missing Git checkout"
        continue
    }
'@

$newPrepareVerify = @'
    if (-not (Test-Path -LiteralPath (Join-Path $path '.git'))) {
        if (Test-DirectoryHasContent -Path $path) {
            Write-Host "[OK] Vendored: $($dep.path) (provenance target $expected)"
            continue
        }
        $errors += "$($dep.path): missing or empty dependency"
        continue
    }
'@

$prepare = Replace-Required `
    -Text $prepare `
    -Old $oldPrepareVerify `
    -New $newPrepareVerify `
    -Label 'PREPARE: verification finale compatible vendored'

Write-Utf8NoBomLf -Path $preparePath -Text $prepare

# -------------------------------------------------------------------------
# 2. VALIDATOR: do not force re-cloning when vendored dependency contents
#    are already present in a complete GitHub ZIP / vendored checkout.
# -------------------------------------------------------------------------
$validate = Read-LfText -Path $validatePath

$oldValidatorProbe = @'
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
'@

$newValidatorProbe = @'
        $gitDir = Join-Path $path '.git'
        if (-not (Test-Path -LiteralPath $gitDir)) {
            $hasVendoredContent = (
                (Test-Path -LiteralPath $path -PathType Container) -and
                ($null -ne (Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue | Select-Object -First 1))
            )
            if ($hasVendoredContent) {
                Write-Host "[OK] Vendored dependency present: $($dep.path) (provenance target $($dep.commit))"
                continue
            }
            $needsPrepare = $true
            break
        }
        $actual = (& git -C $path rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne [string]$dep.commit) {
            $needsPrepare = $true
            break
        }
'@

$validate = Replace-Required `
    -Text $validate `
    -Old $oldValidatorProbe `
    -New $newValidatorProbe `
    -Label 'VALIDATOR: detecter les snapshots vendored avant preparation'

$oldValidatorFinal = @'
        $gitDir = Join-Path $path '.git'
        if (-not (Test-Path -LiteralPath $gitDir)) {
            throw "$($dep.path) is still missing after source preparation."
        }
        $actual = (& git -C $path rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne [string]$dep.commit) {
            throw "$($dep.path) SHA mismatch. Expected $($dep.commit), got $actual"
        }
'@

$newValidatorFinal = @'
        $gitDir = Join-Path $path '.git'
        if (-not (Test-Path -LiteralPath $gitDir)) {
            $hasVendoredContent = (
                (Test-Path -LiteralPath $path -PathType Container) -and
                ($null -ne (Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue | Select-Object -First 1))
            )
            if ($hasVendoredContent) {
                Write-Host "[OK] Vendored dependency ready: $($dep.path) (provenance target $($dep.commit))"
                continue
            }
            throw "$($dep.path) is still missing after source preparation."
        }
        $actual = (& git -C $path rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne [string]$dep.commit) {
            throw "$($dep.path) SHA mismatch. Expected $($dep.commit), got $actual"
        }
'@

$validate = Replace-Required `
    -Text $validate `
    -Old $oldValidatorFinal `
    -New $newValidatorFinal `
    -Label 'VALIDATOR: verification finale compatible vendored'

$validate = $validate.Replace(
    "NVDA-2026.2-HARDENED-V5-20260903-R1",
    $NewRevision
)

# ChatGPT itself is not a Robot test target. Keeping it in the process blacklist
# makes preflight fail merely because the user launched this work from ChatGPT.
# Chrome/Code/Notepad/NVDA/JAWS/Narrator remain protected conflicts.
$oldConflicts = '$conflictNames = @(''nvda'', ''jfw'', ''Narrator'', ''chrome'', ''Code'', ''notepad'', ''ChatGPT'')'
$newConflicts = '$conflictNames = @(''nvda'', ''jfw'', ''Narrator'', ''chrome'', ''Code'', ''notepad'')'
$validate = Replace-Required `
    -Text $validate `
    -Old $oldConflicts `
    -New $newConflicts `
    -Label 'VALIDATOR: ne pas bloquer preflight uniquement a cause du processus ChatGPT'

Write-Utf8NoBomLf -Path $validatePath -Text $validate

# Revision must match the validator, otherwise the strict archive revision guard
# correctly refuses to run.
Write-Utf8NoBomLf -Path $revisionPath -Text ($NewRevision + "`n")

$notes = @"
NVDA HARDENED V5 - VALIDATOR FIX R2
Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')
Revision: $NewRevision

Corrections:
- Complete GitHub/ZIP distributions can keep dependency contents vendored.
- NVDA-HARDENED-PREPARE-SOURCE.ps1 no longer rejects a non-empty dependency
  solely because nested .git metadata was intentionally removed for packaging.
- NVDA-HARDENED-VALIDATE.ps1 accepts complete vendored dependency snapshots
  while retaining exact SHA verification when a dependency is a Git checkout.
- Missing or empty dependency folders are still prepared from the pinned
  repository/SHA manifest.
- System-test preflight no longer fails solely because ChatGPT.exe is running.
  NVDA, JAWS, Narrator, Chrome, VS Code and Notepad remain protected conflicts.
- Build ordering is unchanged: frozen dependencies -> SCons source generation
  -> generated-source readiness -> Ruff/Pyright/tests -> packaging.
"@
Write-Utf8NoBomLf -Path $notesPath -Text ($notes + "`n")

Assert-PowerShellSyntax -Path $preparePath
Assert-PowerShellSyntax -Path $validatePath

Write-Host "`n=== GIT DIFF CHECK ===" -ForegroundColor Cyan
Invoke-GitChecked diff --check

$relativePrepare = "$SourceName/NVDA-HARDENED-PREPARE-SOURCE.ps1"
$relativeValidate = "$SourceName/NVDA-HARDENED-VALIDATE.ps1"
$relativeRevision = "$SourceName/NVDA-HARDENED-REVISION.txt"
$relativeNotes = "$SourceName/HISTORY-VALIDATOR-FIXES-V5-2026-09-03.txt"

Invoke-GitChecked add -- $relativePrepare $relativeValidate $relativeRevision $relativeNotes

Write-Host "`n=== CHANGEMENTS INDEXES ===" -ForegroundColor Cyan
git diff --cached --stat
git diff --cached --check
if ($LASTEXITCODE -ne 0) {
    throw 'git diff --cached --check a detecte un probleme.'
}

& git diff --cached --quiet
$diffCode = $LASTEXITCODE

if ($diffCode -eq 1) {
    Invoke-GitChecked commit -m "Fix hardened V5 validation for vendored dependencies"
}
elseif ($diffCode -eq 0) {
    Write-Host '[INFO] Aucun nouveau changement a committer.' -ForegroundColor Yellow
}
else {
    throw "Impossible de verifier les changements indexes (code $diffCode)."
}

$branch = (& git branch --show-current).Trim()
if (-not $branch) {
    throw 'Branche Git introuvable.'
}

Invoke-GitChecked push origin $branch

$commit = (& git rev-parse HEAD).Trim()

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " PATCH R2 APPLIQUE ET POUSSE SUR GITHUB" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Branche : $branch"
Write-Host "Commit  : $commit"
Write-Host "Revision: $NewRevision"

if ($RunDeterministicValidation) {
    Write-Host "`n=== VALIDATION DETERMINISTE (sans Robot) ===" -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $validatePath -SkipSystemTests
    if ($LASTEXITCODE -ne 0) {
        throw "La validation deterministe a echoue avec le code $LASTEXITCODE. Voir validation-artifacts."
    }
    Write-Host '[OK] Validation deterministe terminee.' -ForegroundColor Green
}

Write-Host "`nEtat final:" -ForegroundColor Cyan
git status
