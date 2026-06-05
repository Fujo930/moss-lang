#define AppName "Moss"
#define AppVersion "0.3.0-alpha"
#define AppPublisher "Codex and Fujo930"

[Setup]
AppId={{36DA50F6-51CB-4DB4-A37A-C6032D14E1A5}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Moss
DefaultGroupName=Moss
OutputDir=..\installer
OutputBaseFilename=Moss-0.3.0-alpha-Windows-Setup
SetupIconFile=moss.ico
UninstallDisplayIcon={app}\Moss Studio.exe
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
LicenseFile=..\LICENSE

[Tasks]
Name: "addtopath"; Description: "Add Moss compiler to PATH"; GroupDescription: "Command line:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\build\windows\Moss\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Moss Studio"; Filename: "{app}\Moss Studio.exe"; WorkingDir: "{userdocs}\Moss Workspace"
Name: "{group}\Moss Command Prompt"; Filename: "{cmd}"; Parameters: "/K ""set PATH={app};%PATH%"""; WorkingDir: "{userdocs}\Moss Workspace"
Name: "{autodesktop}\Moss Studio"; Filename: "{app}\Moss Studio.exe"; Tasks: desktopicon; WorkingDir: "{userdocs}\Moss Workspace"

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Dirs]
Name: "{userdocs}\Moss Workspace"

[Code]
function NeedsAddPath(Param: string): Boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
    OrigPath := '';
  Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(OrigPath) + ';') = 0;
end;
