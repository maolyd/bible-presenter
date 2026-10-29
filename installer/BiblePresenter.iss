; Inno Setup script for Bible Presenter. Built automatically by .github/workflows/build-windows.yml
; (or by hand: iscc /DAppVersion=1.0.0 installer\BiblePresenter.iss after running PyInstaller).

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{410F82A8-CFA4-40AF-931E-CC83C5A709C9}
AppName=Bible Presenter
AppVersion={#AppVersion}
AppVerName=Bible Presenter {#AppVersion}
AppPublisher=Bible Presenter
DefaultDirName={autopf}\Bible Presenter
DefaultGroupName=Bible Presenter
DisableProgramGroupPage=yes
; Installs for the current user without an administrator password; the user may choose "all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=BiblePresenter-Setup-{#AppVersion}
SetupIconFile=..\app\resources\bible-presenter.ico
UninstallDisplayIcon={app}\BiblePresenter.exe
UninstallDisplayName=Bible Presenter
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\BiblePresenter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Bible Presenter"; Filename: "{app}\BiblePresenter.exe"
Name: "{autodesktop}\Bible Presenter"; Filename: "{app}\BiblePresenter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BiblePresenter.exe"; Description: "{cm:LaunchProgram,Bible Presenter}"; Flags: nowait postinstall skipifsilent

; The Bible library and settings live in %LOCALAPPDATA%\BiblePresenter and are kept on uninstall/update.
