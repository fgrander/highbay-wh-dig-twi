# Installs Omniverse Kit outside the repository, from a fixed commit of NVIDIA's template.
# Exit codes: 0 ready, 1 a step failed, 2 the license terms have not been accepted.
# This script never accepts the license terms on anyone's behalf.

param(
    [string]$KitTemplateDir = "C:\dev\omniverse\kit-app-template"
)

$TemplateUrl = "https://github.com/NVIDIA-Omniverse/kit-app-template.git"
$TemplateCommit = "b8e9f2e4f2930d19e87e3702d4eeaf00d9846676"
$TermsUrl = "https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/"
$GeneratedApp = "source\apps\my_company.my_editor.kit"

function Stop-Setup([string]$Message) {
    Write-Error $Message -ErrorAction Continue
    exit 1
}

if (-not (Test-Path (Join-Path $KitTemplateDir ".git"))) {
    Write-Output "Cloning the Kit template to $KitTemplateDir"
    git clone $TemplateUrl $KitTemplateDir
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Cloning the Kit template failed." }
    git -C $KitTemplateDir checkout --quiet $TemplateCommit
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Checking out commit $TemplateCommit failed." }
}

$FoundCommit = git -C $KitTemplateDir rev-parse HEAD
if ($FoundCommit -ne $TemplateCommit) {
    Stop-Setup "$KitTemplateDir is at commit $FoundCommit, but this project needs $TemplateCommit."
}

if (-not (Test-Path (Join-Path $KitTemplateDir ".omniverse_eula_accepted.txt"))) {
    Write-Output "The NVIDIA Omniverse license terms have not been accepted."
    Write-Output "Read them at $TermsUrl"
    Write-Output "To accept them, run this and answer the prompt, then stop it with Ctrl+C and run setup again:"
    Write-Output "  cd $KitTemplateDir"
    Write-Output "  .\repo.bat template new"
    exit 2
}

Push-Location $KitTemplateDir
try {
    if (-not (Test-Path $GeneratedApp)) {
        Write-Output "Creating the template's base application, which provides the dependencies"
        & .\repo.bat template replay .vscode\replay_files\base_editor
        if ($LASTEXITCODE -ne 0) { Stop-Setup "Creating the base application failed." }
    }

    # No application in this setup collects data.
    $Content = Get-Content $GeneratedApp -Raw
    $Off = $Content -replace "telemetry\.enableAnonymousData = true", "telemetry.enableAnonymousData = false"
    if ($Off -cne $Content) {
        [System.IO.File]::WriteAllText((Resolve-Path $GeneratedApp).Path, $Off)
    }

    $KitExe = "_build\windows-x86_64\release\kit\kit.exe"
    if (-not ((Test-Path $KitExe) -and (Test-Path "_build\windows-x86_64\release\extscache"))) {
        Write-Output "Building, which downloads the Kit SDK and its extensions"
        & .\repo.bat build
        if ($LASTEXITCODE -ne 0) { Stop-Setup "Building failed." }
    }
}
finally {
    Pop-Location
}

Write-Output "Omniverse Kit is ready in $KitTemplateDir"
exit 0
