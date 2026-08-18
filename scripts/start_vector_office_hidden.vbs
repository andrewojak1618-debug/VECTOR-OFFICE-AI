Option Explicit

Dim fileSystem, scriptDirectory, shell, command, exitCode
Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
command = "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden " & _
    "-ExecutionPolicy Bypass -File """ & _
    scriptDirectory & "\start_vector_office.ps1"""

exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
