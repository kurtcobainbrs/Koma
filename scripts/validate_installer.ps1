param([Parameter(Mandatory=$true)][string]$Installer, [switch]$FullFileCheck)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$setup = (Resolve-Path -LiteralPath $Installer).Path
$release = Split-Path $setup -Parent
$metadata = Get-Content -LiteralPath (Join-Path $release 'build-info.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$work = Join-Path $root ('build\install-validation-' + [guid]::NewGuid().ToString('N'))
$appDir = [IO.Path]::GetFullPath((Join-Path $work 'Koma'))
$buildRoot = [IO.Path]::GetFullPath((Join-Path $root 'build')).TrimEnd('\') + '\'
if (-not $appDir.StartsWith($buildRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Destino de validação fora de build/.' }
$definition = Get-Content -LiteralPath (Join-Path $root 'packaging/windows/installer.iss') -Raw
$match = [regex]::Match($definition, 'AppId=\{\{([A-Fa-f0-9-]+)\}')
if (-not $match.Success) { throw 'AppId do instalador não encontrado.' }
$keyName = '{' + $match.Groups[1].Value + '}_is1'
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $keyName
if (Test-Path -LiteralPath $uninstallKey) { throw 'Já há uma instalação registrada do Koma. Valide em Windows limpo para preservá-la.' }
New-Item -ItemType Directory -Path $work | Out-Null
$report = [ordered]@{ ok=$false; installer=(Split-Path $setup -Leaf); installed_files_verified=0; diagnostics=$false; uninstalled=$false; user_data_preserved=$false }
$installed = $false
try {
    Write-Output 'Instalando em uma pasta isolada...'
    $arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/TASKS=',('/DIR="' + $appDir + '"'),('/LOG="' + (Join-Path $work 'setup.log') + '"'))
    $process = Start-Process -FilePath $setup -ArgumentList $arguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) { throw 'A instalação excedeu o tempo de validação.' }
    if ($process.ExitCode -ne 0) { throw "Falha na instalação: $($process.ExitCode)" }
    $registration = Get-ItemProperty -LiteralPath $uninstallKey
    if ([IO.Path]::GetFullPath($registration.InstallLocation).TrimEnd('\') -ne $appDir.TrimEnd('\')) { throw 'O instalador registrou um destino inesperado.' }
    $installed = $true
    $files = if ($FullFileCheck) { $metadata.files } else {
        $metadata.files | Where-Object { $_.path -eq 'Koma.exe' -or $_.path -eq '_internal/desktop/flet/flet.exe' -or $_.path -like '_internal/_miniaudio*.pyd' }
    }
    foreach ($entry in $files) {
        $path = [IO.Path]::GetFullPath((Join-Path $appDir $entry.path))
        if (-not $path.StartsWith($appDir.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Caminho inválido no manifesto da release.' }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Arquivo instalado diferente: $($entry.path)" }
        $report.installed_files_verified++
    }
    Write-Output 'Executando diagnóstico do aplicativo instalado...'
    $diagnosticPath = Join-Path $work 'diagnostics.json'
    $process = Start-Process -FilePath (Join-Path $appDir 'Koma.exe') -ArgumentList @('--diagnostics',('"' + $diagnosticPath + '"')) -WorkingDirectory $appDir -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) { throw 'O diagnóstico excedeu o tempo de validação.' }
    if ($process.ExitCode -ne 0) { throw 'O aplicativo instalado falhou no diagnóstico.' }
    $diagnostics = Get-Content -LiteralPath $diagnosticPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $diagnostics.ok -or -not $diagnostics.frozen) { throw 'O diagnóstico não confirmou o pacote instalado.' }
    $report.diagnostics = $true
    $sample = Join-Path $diagnostics.artifacts 'exemplo.koma'
    $before = (Get-FileHash -LiteralPath $sample -Algorithm SHA256).Hash
    Write-Output 'Desinstalando e conferindo a preservação do projeto de teste...'
    $uninstaller = Join-Path $appDir 'unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'Desinstalador ausente.' }
    $process = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="' + (Join-Path $work 'uninstall.log') + '"')) -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) { throw 'A desinstalação excedeu o tempo de validação.' }
    if ($process.ExitCode -ne 0 -or (Test-Path -LiteralPath (Join-Path $appDir 'Koma.exe')) -or (Test-Path -LiteralPath $uninstallKey)) { throw 'A desinstalação não foi concluída.' }
    $installed = $false
    $report.uninstalled = $true
    $report.user_data_preserved = (Get-FileHash -LiteralPath $sample -Algorithm SHA256).Hash -eq $before
    $report.ok = $report.diagnostics -and $report.uninstalled -and $report.user_data_preserved
    if (-not $report.ok) { throw 'A validação do instalador falhou.' }
} finally {
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $work 'report.json') -Encoding UTF8
    if ($installed) { Write-Warning "A instalação de teste foi preservada para inspeção em $appDir" }
}
Write-Output "Instalador validado. Relatório: $work\report.json"
