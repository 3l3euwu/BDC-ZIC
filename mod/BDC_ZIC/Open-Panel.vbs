' Start the GUI with the windowless Python launcher; no command prompt is opened.
Option Explicit
Dim shell, fso, scriptDir, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
command = "pyw.exe -3 " & Chr(34) & fso.BuildPath(scriptDir, "panel\panel.py") & Chr(34)
On Error Resume Next
shell.Run command, 0, False
If Err.Number <> 0 Then
    MsgBox "Could not launch the panel. Install Python 3 with the Windows Python launcher and Tkinter." & vbCrLf & Err.Description, vbExclamation, "BDC-ZIC"
End If
