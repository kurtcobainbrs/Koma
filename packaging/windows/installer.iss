; As versões e os caminhos vêm do construtor, não de um diretório pessoal.
#ifndef AppVersion
  #error AppVersion não foi informado
#endif
#ifndef PackageDir
  #error PackageDir não foi informado
#endif
#ifndef ReleaseDir
  #error ReleaseDir não foi informado
#endif
#ifndef AppIcon
  #error AppIcon não foi informado
#endif

[Setup]
AppId={{B461B51B-CC6A-53E5-9D32-2433A935DE14}
AppName=Koma
AppVersion={#AppVersion}
AppVerName=Koma {#AppVersion}
AppPublisher=Koma
AppPublisherURL=https://github.com/kurtcobainbrs/Koma
AppSupportURL=https://github.com/kurtcobainbrs/Koma/issues
AppUpdatesURL=https://github.com/kurtcobainbrs/Koma/releases
DefaultDirName={localappdata}\Programs\Koma
DefaultGroupName=Koma
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#ReleaseDir}
OutputBaseFilename=Koma-{#AppVersion}-windows-x64-setup
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\Koma.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes
VersionInfoVersion={#AppVersion}.0
VersionInfoDescription=Instalador Koma
VersionInfoProductName=Koma

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked
Name: "openwith"; Description: "Adicionar Koma às opções de Abrir com para arquivos .koma"; Flags: unchecked

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Koma"; Filename: "{app}\Koma.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Koma"; Filename: "{app}\Koma.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\.koma\OpenWithProgids"; ValueType: string; ValueName: "Koma.Project"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKCU; Subkey: "Software\Classes\Koma.Project"; ValueType: string; ValueData: "Projeto Koma"; Flags: uninsdeletekey; Tasks: openwith
Root: HKCU; Subkey: "Software\Classes\Koma.Project\DefaultIcon"; ValueType: string; ValueData: "{app}\Koma.exe,0"; Tasks: openwith
Root: HKCU; Subkey: "Software\Classes\Koma.Project\shell\open\command"; ValueType: string; ValueData: """{app}\Koma.exe"" ""%1"""; Tasks: openwith

[Run]
Filename: "{app}\Koma.exe"; Description: "Abrir Koma"; Flags: nowait postinstall skipifsilent
