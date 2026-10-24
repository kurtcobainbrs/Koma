param(
    [string]$Kit = $PSScriptRoot,
    [string]$Destination = (Join-Path ([Environment]::GetFolderPath('Desktop')) ('Koma-validacao-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))),
    [string]$Blender = '',
    [switch]$NoLaunch
)
$ErrorActionPreference = 'Stop'
# Não sobrescreve uma validação anterior nem altera configurações do sistema.
if (Test-Path -LiteralPath $Destination) { throw 'Escolha uma pasta de destino nova.' }
$destinationPath = [IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Path $destinationPath | Out-Null
$kitPath = (Resolve-Path -LiteralPath $Kit).Path
$manifest = Get-Content -LiteralPath (Join-Path $kitPath 'SHA256.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($entry in $manifest) {
    $file = [IO.Path]::GetFullPath((Join-Path $kitPath $entry.path))
    if (-not $file.StartsWith($kitPath.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Caminho inválido no manifesto.' }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Hash diferente: $($entry.path)" }
}
Copy-Item -LiteralPath (Join-Path $kitPath 'Koma') -Destination $destinationPath -Recurse
$results = Join-Path $destinationPath 'resultados'
New-Item -ItemType Directory -Path $results | Out-Null
$env:KOMA_DATA_DIR = Join-Path $results 'dados'
$environmentReport = [ordered]@{
    Windows = [Environment]::OSVersion.VersionString
    Architecture = $env:PROCESSOR_ARCHITECTURE
    PythonCommand = @(Get-Command python,python3,py -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    JavaCommand = @(Get-Command java -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    FletCacheExists = (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.flet'))
    VCRegistry = @(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue | Select-Object Version,Installed)
    PackageHashesVerified = $true
    NetworkIsolation = 'Confirmar manualmente; o script não muda a configuração de rede.'
}
$environmentReport | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $results 'ambiente.json') -Encoding UTF8
$executable = Join-Path $destinationPath 'Koma\Koma.exe'
$report = Join-Path $results 'diagnostics.json'
$arguments = @('--diagnostics', ('"' + $report + '"'))
if ($Blender) { $arguments += @('--blender', ('"' + $Blender + '"')) }
$process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $destinationPath -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw "Diagnóstico falhou. Consulte $results" }
$diagnostics = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $diagnostics.ok -or -not $diagnostics.frozen) { throw 'O diagnóstico não confirmou a instalação empacotada.' }
$sample = Join-Path $diagnostics.artifacts 'exemplo.koma'
Write-Output "Diagnóstico aprovado. Relatórios e amostras: $results"
if (-not $NoLaunch) {
    # Janela interativa solicitada para executar o roteiro manual do kit.
    Start-Process -FilePath $executable -ArgumentList ('"' + $sample + '"') -WorkingDirectory $destinationPath -WindowStyle Normal | Out-Null
}
