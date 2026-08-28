Option Explicit
Dim shell, fso, root, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
command = "pythonw.exe """ & root & "\START_VIDEO_FACTORY.py"""
shell.CurrentDirectory = root
shell.Run command, 0, False

