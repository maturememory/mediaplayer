#define MyAppName "Nova Media Player"
#define MyAppPublisher "Nova Media Player"
#define MyAppVersion "1.0.0"
#define MyAppExeName "NovaMediaPlayer.exe"
#define MyAppAssocName "Nova Media File"
#define MyAppAssocExts "mp4,mkv,avi,mov,wmv,flv,webm,m4v,mpeg,mpg,3gp,3g2,ts,mts,m2ts,vob,ogv,rm,rmvb,divx,asf,f4v,dv,m2v,hevc,h264,h265,mxf,wtv,dvr-ms,mp3,flac,wav,aac,ogg,wma,m4a,opus,ape,aiff,aif,mka,ac3,dts,amr,ra,wv,tta,caf,mid,midi,alac,spx,tak,mpc,mp2,gsm,au,snd,jpg,jpeg,png,gif,bmp,webp,tiff,tif,ico,heic,heif,avif,psd,raw,cr2,nef,arw,dng,orf,sr2,rw2,pef,svg,xbm,pcx,tga,pbm,pgm,ppm,xpm"

[Setup]
AppId={{0F588894-C5A3-4D43-AF60-5217F783C80D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/
AppSupportURL=https://github.com/
AppUpdatesURL=https://github.com/
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
DisableProgramGroupPage=yes
LicenseFile=README.md
OutputDir=..\..\dist\installer
OutputBaseFilename=NovaMediaPlayerSetup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "associatefiles"; Description: "Register Nova Media Player as an option for supported media files"; GroupDescription: "Windows integration:"; Flags: checkedonce

[Files]
Source: "..\..\dist\Nova Media Player\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCR; Subkey: "Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKCR; Subkey: "{#MyAppAssocName}"; ValueType: string; ValueData: "{#MyAppAssocName}"; Tasks: associatefiles; Flags: uninsdeletekey
Root: HKCR; Subkey: "{#MyAppAssocName}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"; Tasks: associatefiles
Root: HKCR; Subkey: "{#MyAppAssocName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: associatefiles

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
Filename: "https://www.videolan.org/vlc/download-windows.html"; Description: "Download VLC Media Player (required for video/audio playback)"; Flags: shellexec postinstall skipifsilent unchecked
Filename: "https://github.com/BtbN/FFmpeg-Builds/releases"; Description: "Download FFmpeg (required for AI subtitles)"; Flags: shellexec postinstall skipifsilent unchecked

[Code]
const
  AssocExtCsv = '{#MyAppAssocExts}';

function TakeCsvItem(var Csv: String): String;
var
  PosComma: Integer;
begin
  PosComma := Pos(',', Csv);
  if PosComma = 0 then
  begin
    Result := Csv;
    Csv := '';
  end
  else
  begin
    Result := Copy(Csv, 1, PosComma - 1);
    Delete(Csv, 1, PosComma);
  end;
end;

procedure RegisterFileAssociations;
var
  Csv: String;
  Ext: String;
begin
  if not WizardIsTaskSelected('associatefiles') then
    exit;

  Csv := AssocExtCsv;
  while Csv <> '' do
  begin
    Ext := TakeCsvItem(Csv);
    if Ext <> '' then
      RegWriteStringValue(HKEY_CLASSES_ROOT, '.' + Ext + '\OpenWithProgids', '{#MyAppAssocName}', '');
  end;
end;

procedure UnregisterFileAssociations;
var
  Csv: String;
  Ext: String;
begin
  Csv := AssocExtCsv;
  while Csv <> '' do
  begin
    Ext := TakeCsvItem(Csv);
    if Ext <> '' then
      RegDeleteValue(HKEY_CLASSES_ROOT, '.' + Ext + '\OpenWithProgids', '{#MyAppAssocName}');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RegisterFileAssociations;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    UnregisterFileAssociations;
end;
