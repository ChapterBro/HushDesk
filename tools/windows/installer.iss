[Setup]
AppName=HushDesk
AppVersion=0.1.0
DefaultDirName={pf}\HushDesk
DefaultGroupName=HushDesk
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=HushDesk_Setup

[Files]
Source: "dist\HushDesk.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\HushDesk"; Filename: "{app}\HushDesk.exe"

[Run]
Filename: "{app}\HushDesk.exe"; Parameters: "self-check"; Description: "Run self-check"; Flags: postinstall
