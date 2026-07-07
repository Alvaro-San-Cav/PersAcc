' Lanzador silencioso de PersAcc (FastAPI + Chrome app). Evita instancias duplicadas.
Dim objWMIService, colProcessList
Set objWMIService = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")

' Si ya hay un Chrome abierto con nuestro perfil, avisar y salir
Set colProcessList = objWMIService.ExecQuery("Select * from Win32_Process Where Name LIKE 'chrome%' AND CommandLine LIKE '%PersAccChromeProfile%'")
If colProcessList.Count > 0 Then
    MsgBox "PersAcc ya esta abierto.", 64, "PersAcc"
    WScript.Quit
End If

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\run_persacc_app.bat" & Chr(34), 0
Set WshShell = Nothing
