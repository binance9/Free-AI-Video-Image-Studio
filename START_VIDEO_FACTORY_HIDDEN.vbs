Option Explicit
Dim shell, fso, root, command, pySite
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pySite = "C:\Users\BAOAN\AppData\Roaming\Python\Python314\site-packages"
shell.Environment("Process").Item("PYTHONPATH") = pySite
command = "C:\Python314\pythonw.exe """ & root & "\START_VIDEO_FACTORY.py"""
shell.CurrentDirectory = root
shell.Run command, 0, False

