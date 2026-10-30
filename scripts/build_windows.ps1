param(
    [string]$Python = '.venv\Scripts\python.exe',
    [switch]$FullTests,
    [switch]$IncludePythonArtifacts,
    [switch]$ValidationKit
)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if ($FullTests) {
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam.' }
    }
    & $Python scripts\prepare_release_resources.py
    if ($LASTEXITCODE -ne 0) { throw 'Os recursos da release não foram preparados.' }
    $clientArguments = @('scripts\build_flet_client.py')
    if ($FullTests) { $clientArguments += '--full-tests' }
    & $Python @clientArguments
    if ($LASTEXITCODE -ne 0) { throw 'O cliente Flet com drop nativo não foi validado.' }
    & $Python -c "from pathlib import Path; from scripts.prepare_release_resources import third_party_notices; from koma.ui.drop_runtime import development_client; root=Path.cwd(); third_party_notices(root, root/'build/release/licenses', development_client(root))"
    if ($LASTEXITCODE -ne 0) { throw 'Os avisos de terceiros não foram preparados.' }
    New-Item -ItemType Directory -Path build -Force | Out-Null
    $stage = Join-Path $PWD ('build\windows-stage-' + [guid]::NewGuid().ToString('N'))
    $package = Join-Path $stage 'Koma'
    $buildPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 treats native stderr as an error record. PyInstaller
        # writes progress there too; its exit code determines whether it failed.
        $ErrorActionPreference = 'Continue'
        & $Python -m PyInstaller --noconfirm --distpath $stage Koma.spec 2>&1 | Tee-Object -FilePath build\pyinstaller.log
        $buildExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $buildPreference
    }
    if ($buildExitCode -ne 0) { throw 'O build Windows falhou.' }
    if (Select-String -Path build\pyinstaller.log -SimpleMatch 'Library not found:') {
        throw 'O PyInstaller encontrou dependências nativas ausentes.'
    }
    foreach ($resource in @(
        '_internal\koma\assets\fonts\Archivo-Regular.ttf',
        '_internal\koma\assets\storyboard-subtitles.json',
        '_internal\desktop\flet\flet.exe',
        '_internal\desktop\flet\koma-client.json',
        '_internal\desktop\flet\data\flutter_assets\fonts\MaterialIcons-Regular.otf'
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $package $resource) -PathType Leaf)) { throw "Recurso ausente: $resource" }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $package '_internal\av.libs') -PathType Container)) {
        throw 'As bibliotecas de vídeo do PyAV estão ausentes.'
    }
    & $Python scripts\windows_native.py --directory $package
    if ($LASTEXITCODE -ne 0) { throw 'A auditoria das DLLs falhou.' }
    $diagnosticsReport = Join-Path $PWD 'build\packaged-diagnostics.json'
    $diagnosticsProcess = Start-Process -FilePath (Join-Path $package 'Koma.exe') -ArgumentList @('--diagnostics', ('"' + $diagnosticsReport + '"'), '--video') -WorkingDirectory $package -WindowStyle Hidden -PassThru
    if (-not $diagnosticsProcess.WaitForExit(60000)) {
        Stop-Process -Id $diagnosticsProcess.Id
        throw 'O diagnóstico do executável excedeu 60 segundos.'
    }
    if ($diagnosticsProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $diagnosticsReport)) { throw 'O diagnóstico do executável falhou.' }
    $diagnostics = Get-Content -LiteralPath $diagnosticsReport -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $diagnostics.ok -or -not $diagnostics.frozen) { throw 'O pacote falhou no diagnóstico offline.' }
    & $Python scripts\publish_windows_package.py $package
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível publicar o pacote; a versão anterior foi preservada.' }
    if ($IncludePythonArtifacts) {
        & $Python -m build --no-isolation
        if ($LASTEXITCODE -ne 0) { throw 'O build Python falhou.' }
    }
    if ($ValidationKit) {
        & $Python scripts\prepare_windows_validation.py
        if ($LASTEXITCODE -ne 0) { throw 'A criação do kit de validação falhou.' }
    }
    Write-Output 'Distribuição em dist\Koma\Koma.exe. Distribua a pasta Koma inteira.'
} finally {
    Pop-Location
}
