Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
projectPath = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = projectPath & "\run_morning_brief.ps1"

cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & scriptPath & Chr(34)

WScript.Quit shell.Run(cmd, 0, True)
