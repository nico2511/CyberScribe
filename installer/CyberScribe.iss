; CyberScribe Windows installer (Inno Setup 6)
; Build: ISCC.exe /DMyAppVersion=1.4.0 installer\CyberScribe.iss

#ifndef MyAppVersion
  #define MyAppVersion "1.4.0"
#endif

#define MyAppName "CyberScribe"
#define MyAppPublisher "CyberScribe"
#define MyAppExeName "CyberScribe.exe"

[Setup]
AppId={{A7B4E2C1-9D3F-4A8B-8C5E-1F2D3E4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=CyberScribe-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ModelsDirPage: TInputDirWizardPage;

function JsonEscapePath(const S: string): string;
var
  I: Integer;
  C: Char;
  R: string;
begin
  R := '';
  for I := 1 to Length(S) do
  begin
    C := S[I];
    if C = '\' then
      R := R + '\\'
    else if C = '"' then
      R := R + '\"'
    else
      R := R + C;
  end;
  Result := R;
end;

function ModelsDirForConfig(const AbsolutePath: string): string;
var
  LocalApp: string;
begin
  LocalApp := ExpandConstant('{localappdata}');
  if (Length(AbsolutePath) >= Length(LocalApp)) and
     (CompareText(Copy(AbsolutePath, 1, Length(LocalApp)), LocalApp) = 0) then
    Result := '%LOCALAPPDATA%' + Copy(AbsolutePath, Length(LocalApp) + 1, MaxInt)
  else
    Result := AbsolutePath;
end;

procedure InitializeWizard;
begin
  ModelsDirPage := CreateInputDirPage(wpSelectDir,
    'Dossier des modèles Whisper',
    'Où télécharger les modèles ? (plusieurs centaines de Mo possibles)',
    'Vous pourrez modifier ce chemin plus tard dans Configuration.',
    False, 'models');
  ModelsDirPage.Add('Dossier des modèles :');
  ModelsDirPage.Values[0] := ExpandConstant('{localappdata}\CyberScribe\models');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, ModelsAbs, ModelsCfg, Json: string;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigPath := ExpandConstant('{app}\config.json');
    if not FileExists(ConfigPath) then
    begin
      ModelsAbs := ModelsDirPage.Values[0];
      ModelsCfg := JsonEscapePath(ModelsDirForConfig(ModelsAbs));
      Json :=
        '{' + #13#10 +
        '    "hotkey": "F8",' + #13#10 +
        '    "language": "fr",' + #13#10 +
        '    "model_size": "base",' + #13#10 +
        '    "device": "auto",' + #13#10 +
        '    "compute_type": "int8",' + #13#10 +
        '    "transcription_profile": "fast",' + #13#10 +
        '    "max_record_seconds": 25,' + #13#10 +
        '    "check_updates": true,' + #13#10 +
        '    "models_dir": "' + ModelsCfg + '"' + #13#10 +
        '}';
      SaveStringToFile(ConfigPath, Json, False);
    end;
  end;
end;
