Set WshShell = CreateObject("WScript.Shell")
set fs = CreateObject("Scripting.FileSystemObject")
' set current dir to script dir
WshShell.CurrentDirectory = fs.GetParentFolderName(fs.GetParentFolderName(WScript.ScriptFullName))
WshShell.Run ".suivi\scripts\pythonw suivi.py"
