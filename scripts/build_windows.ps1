param([string]$Python = '.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & $Python -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam.' }
    New-Item -ItemType Directory -Path build -Force | Out-Null
    & $Python -m PyInstaller --noconfirm Koma.spec 2>&1 | Tee-Object -FilePath build\pyinstaller.log
    if ($LASTEXITCODE -ne 0) { throw 'O build Windows falhou.' }
    if (Select-String -Path build\pyinstaller.log -SimpleMatch 'Library not found:') {
        throw 'O PyInstaller encontrou dependências nativas ausentes.'
    }
    foreach ($resource in @(
        'dist\Koma\_internal\koma\exports\blender_probe.py',
        'dist\Koma\_internal\koma\assets\fonts\Archivo-Regular.ttf',
        'dist\Koma\_internal\koma\assets\storyboard-subtitles.json',
        'dist\Koma\_internal\desktop\flet\flet.exe'
    )) {
        if (-not (Test-Path -LiteralPath $resource -PathType Leaf)) { throw "Recurso ausente: $resource" }
    }
    & $Python scripts\windows_native.py
    if ($LASTEXITCODE -ne 0) { throw 'A auditoria das DLLs falhou.' }
    $diagnosticsReport = Join-Path $PWD 'build\packaged-diagnostics.json'
    $diagnosticsProcess = Start-Process -FilePath (Join-Path $PWD 'dist\Koma\Koma.exe') -ArgumentList @('--diagnostics', ('"' + $diagnosticsReport + '"')) -WorkingDirectory (Join-Path $PWD 'dist\Koma') -WindowStyle Hidden -PassThru
    if (-not $diagnosticsProcess.WaitForExit(60000)) {
        Stop-Process -Id $diagnosticsProcess.Id
        throw 'O diagnóstico do executável excedeu 60 segundos.'
    }
    if ($diagnosticsProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $diagnosticsReport)) { throw 'O diagnóstico do executável falhou.' }
    $diagnostics = Get-Content -LiteralPath $diagnosticsReport -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $diagnostics.ok -or -not $diagnostics.frozen) { throw 'O pacote falhou no diagnóstico offline.' }
    & $Python -m build --no-isolation
    if ($LASTEXITCODE -ne 0) { throw 'O build Python falhou.' }
    & $Python scripts\prepare_windows_validation.py
    if ($LASTEXITCODE -ne 0) { throw 'A criação do kit de validação falhou.' }
    Write-Output 'Distribuição em dist\Koma\Koma.exe. Distribua a pasta Koma inteira.'
} finally {
    Pop-Location
}
