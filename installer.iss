; Inno Setup — створює WAVE_Launcher_Setup.exe зі звичайним майстром встановлення
#define MyAppName "WAVE LAUNCHER"
#ifndef MyAppVersion
  #define MyAppVersion "3.0"
#endif
#define MyAppExe "WAVELauncher.exe"

[Setup]
AppId={{B7C1D2A4-5E3F-4A86-9C1B-0A1B2C3D4E5F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\WAVE Launcher
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=WAVE_Launcher_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon.ico
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExe}

[Languages]
#if FileExists(CompilerPath + "Languages\Ukrainian.isl")
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Створити ярлик на робочому столі"; Flags: checkedonce

[Files]
Source: "dist\WAVELauncher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{autodesktop}\MyCraft Launcher.lnk"
Type: filesandordirs; Name: "{autoprograms}\MyCraft Launcher"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Запустити {#MyAppName}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExe}"; Flags: nowait; Check: WizardSilent
