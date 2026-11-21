# PowerShell 5.1+ / 7: safely launch a synthetic-only live TokenDance Tool Calling test.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/accept_tokendance.ps1
# This script does not store a key in a file, GitHub, command history, or output.
param(
    [string]$Model = ""
)
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($Model)) {
    $Model = (Read-Host "TokenDance Chat Completions model ID (must support tools)").Trim()
}
if ($Model -notmatch '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}$') {
    Write-Error "Invalid model ID. Copy a supported Chat Completions model ID from your provider console."
    exit 2
}

Write-Host "Only synthetic budget/coverage/inventory aggregates will be sent to tokendance.space."
Write-Host "The original CompanyAgent run and all business data will remain unchanged."
Write-Host "A live model request may consume provider credits."
$approval = Read-Host "Type YES to authorize this one live external tool-calling run"
if ($approval -cne "YES") {
    Write-Host "Not executed: explicit consent was not given."
    exit 2
}

$secret = Read-Host "Newly rotated TokenDance API Key (hidden)" -AsSecureString
$bstr = [IntPtr]::Zero
$exitCode = 2
$locationChanged = $false
try {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    $keyValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($keyValue)) {
        throw "Empty API Key; no network request was made."
    }
    $env:COMPANYAGENT_MODEL_PROVIDER = "tokendance"
    $env:TOKENDANCE_MODEL = $Model
    $env:TOKENDANCE_API_KEY = $keyValue
    $keyValue = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    $bstr = [IntPtr]::Zero

    Push-Location $repoRoot
    $locationChanged = $true
    & python scripts/verify_tokendance_tool_calling.py --i-authorize-external-call
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 1 }
} catch {
    # Never echo an exception that might include user input or environment values.
    Write-Host "The local acceptance runner did not complete. Check Python installation and connectivity."
    $exitCode = 2
} finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    Remove-Item Env:\TOKENDANCE_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\TOKENDANCE_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:\COMPANYAGENT_MODEL_PROVIDER -ErrorAction SilentlyContinue
    if ($locationChanged) { Pop-Location }
}
if ($exitCode -eq 0) {
    Write-Host "Live Tool Calling acceptance runner reported PASS. Verify tool trace, quota, and provider logs."
} else {
    Write-Host "Live Tool Calling acceptance NOT verified (exit $exitCode)."
}
exit $exitCode
