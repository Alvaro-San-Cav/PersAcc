Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\scripts\run_persacc.bat" & Chr(34), 0
Set WshShell = Nothing
