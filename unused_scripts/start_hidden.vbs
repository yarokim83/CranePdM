Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = currentDir

' 0 = Hide window, False = don't wait for completion
WshShell.Run "pythonw.exe crane_edge_logger.py", 0, False
