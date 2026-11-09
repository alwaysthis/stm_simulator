Option Explicit
Dim sh, fso, root, py, folder, candidate, command, code
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
py = ""
If fso.FileExists(root & "\.venv\Scripts\pythonw.exe") Then py = root & "\.venv\Scripts\pythonw.exe"
If py = "" Then
    For Each folder In Split(sh.ExpandEnvironmentStrings("%PATH%"), ";")
        folder = Replace(Trim(folder), Chr(34), "")
        If folder <> "" Then
            candidate = fso.BuildPath(folder, "pythonw.exe")
            If fso.FileExists(candidate) Then
                py = candidate
                Exit For
            End If
        End If
    Next
End If
If py = "" Then
    MsgBox "Python was not found. Install Python with tkinter, numpy and scipy, or create .venv.", 16, "STM Simulator"
    WScript.Quit 1
End If
sh.CurrentDirectory = root
command = Chr(34) & py & Chr(34) & " " & Chr(34) & root & "\run.py" & Chr(34)
code = sh.Run(command, 0, True)
If code <> 0 Then MsgBox "Startup failed. See startup-error.log in the application folder.", 16, "STM Simulator"
