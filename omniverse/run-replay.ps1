# Opens a run folder in the Omniverse replay. Any further arguments go to Kit. The script ends when
# the application closes.

param(
    [string]$RunFolder = "",
    [string]$KitTemplateDir = "C:\dev\omniverse\kit-app-template",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$KitArguments = @()
)

$Release = Join-Path $KitTemplateDir "_build\windows-x86_64\release"
$KitExe = Join-Path $Release "kit\kit.exe"
if (-not (Test-Path $KitExe)) {
    Write-Error "Omniverse Kit was not found in $KitTemplateDir. Run omniverse/setup.ps1 first." -ErrorAction Continue
    exit 1
}

$Arguments = @(
    (Join-Path $PSScriptRoot "highbay.replay.app.kit"),
    "--ext-folder", (Join-Path $PSScriptRoot "exts"),
    "--ext-folder", (Join-Path $Release "extscache")
)
if ($RunFolder) {
    # A missing folder is reported by the application, like any other unusable run folder.
    $Folder = [System.IO.Path]::GetFullPath($RunFolder)
    $Arguments += "--/exts/highbay.replay/run_folder=$Folder"
}

& $KitExe @Arguments @KitArguments
exit $LASTEXITCODE
