param([string]$Kit = $PSScriptRoot, [string]$Output = (Join-Path $PSScriptRoot 'Koma-clean.wsb'))
$ErrorActionPreference = 'Stop'
$path = [Security.SecurityElement]::Escape((Resolve-Path -LiteralPath $Kit).Path)
@"
<Configuration>
  <Networking>Disable</Networking>
  <MemoryInMB>4096</MemoryInMB>
  <MappedFolders>
    <MappedFolder><HostFolder>$path</HostFolder><SandboxFolder>C:\KomaSource</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>C:\KomaSource\Koma\Koma.exe --diagnostics C:\KomaValidation\diagnostics.json</Command></LogonCommand>
</Configuration>
"@ | Set-Content -LiteralPath $Output -Encoding UTF8
Write-Output "Configuração criada: $Output. Abra-a em um host com Windows Sandbox já disponível."
