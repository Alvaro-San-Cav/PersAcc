' Check if application is already running to prevent multiple instances
Dim objWMIService, colProcessList, p
Set objWMIService = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")

' 1. Check if Chrome is already running with our specific profile
Set colProcessList = objWMIService.ExecQuery("Select * from Win32_Process Where Name LIKE 'chrome%' AND CommandLine LIKE '%PersAccChromeProfile%'")
If colProcessList.Count > 0 Then
    MsgBox "PersAcc ya esta abierto.", 64, "PersAcc"
    WScript.Quit
End If

' 2. Check if Python/Streamlit is already initializing (race condition window)
Set colProcessList = objWMIService.ExecQuery("Select * from Win32_Process Where Name LIKE 'python%' AND CommandLine LIKE '%streamlit run app.py%'")
If colProcessList.Count > 0 Then
    MsgBox "PersAcc se esta iniciando, por favor espera...", 64, "PersAcc"
    WScript.Quit
End If

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\run_persacc.bat" & Chr(34), 0
Set WshShell = Nothing
