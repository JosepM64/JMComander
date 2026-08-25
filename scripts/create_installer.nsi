; -*- coding: utf-8 -*-
;
; Script de instalador NSIS para JMComander
; Crea un instalador Windows profesional

[Setup]
AppName=JMComander
AppPublisher=JMSoftware
AppVersion=1.0.0
DefaultDirName={pf}\JMComander
DefaultGroupName=JMComander
AllowNoIcons=yes
Compression=lzma
SolidCompression=yes
OutputBaseFilename=JMComander_Setup

[Languages]
Name=Spanish
Name=English

[Files]
Source: "dist\JMComander_mejorado\JMComander_mejorado.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\JMComander_mejorado\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "JMComander"; Filename: "{app}\JMComander_mejorado.exe"; IconIndex: 0

[Run]
Filename: "{app}\JMComander_mejorado.exe"; Description: "Iniciar JMComander"

[UninstallDelete]
Delete: "{app}\_internal\*"; Delete: "{app}\JMComander_mejorado.exe"
