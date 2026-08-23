; Script Inno Setup del instalador oficial del Visor de Videos.
; Compatible con Inno Setup 6.7.3. Instalacion por usuario, sin permisos
; de administrador, destino %LOCALAPPDATA%\Programs\VisorVideos.
;
; Para futuras versiones: pasar /DAplicacionVersion=X.Y y /DBetaEtiqueta=BetaN
; al compilador o editar los #define por defecto.
;
; Ejemplo:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAplicacionVersion=7.0 /DBetaEtiqueta=Beta7 instalador.iss

#ifndef AplicacionVersion
  #define AplicacionVersion "7.0"
#endif

#ifndef BetaEtiqueta
  #define BetaEtiqueta "Beta7"
#endif

[Setup]
; GUID fijo del producto (por usuario), independiente de Beta1/Beta2
AppId={{3A5B7C9D-E1F2-4A3B-9C8D-0E1F2A3B4C5D}
AppName=Visor de Videos
AppVersion={#AplicacionVersion}
AppVerName=Visor de Videos {#AplicacionVersion}
AppPublisher=Visor de Videos
DefaultDirName={localappdata}\Programs\VisorVideos
DefaultGroupName=Visor de Videos
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Distribucion\{#BetaEtiqueta}
OutputBaseFilename=VisorVideos_{#BetaEtiqueta}_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\VisorVideos.exe
SetupLogging=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
; Ejecutable y bibliotecas empaquetadas por PyInstaller (dist\VisorVideos\)
Source: "dist\VisorVideos\VisorVideos.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\VisorVideos\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; Base de datos vacia con el esquema vigente (se genera en el paso previo del build;
; onlyifdoesntexist preserva el catalogo del usuario en reinstalaciones;
; uninsneveruninstall conserva la base y los datos del usuario al desinstalar)
Source: "dist\VisorVideos\biblioteca.db"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\Visor de Videos"; Filename: "{app}\VisorVideos.exe"
Name: "{autodesktop}\Visor de Videos"; Filename: "{app}\VisorVideos.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VisorVideos.exe"; Description: "Ejecutar Visor de Videos"; Flags: nowait postinstall skipifsilent

; Beta 6 / B6.1: la desinstalacion NO borra {app} recursivamente.
; Los binarios instalados desde [Files] se eliminan de forma normal; los datos
; persistentes del usuario (biblioteca.db, configuracion.json, miniaturas/) se
; conservan al desinstalar para permitir una reinstalacion sin perdida de datos.
