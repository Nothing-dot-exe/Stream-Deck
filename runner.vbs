Set WshShell = CreateObject("WScript.Shell")
' Get the directory where this script is located
strPath = WScript.ScriptFullName
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objFile = objFSO.GetFile(strPath)
strFolder = objFSO.GetParentFolderName(objFile)

' Change working directory
WshShell.CurrentDirectory = strFolder

' Run the unified app in headless mode (server only, no GUI) silently
WshShell.Run "venv\Scripts\pythonw.exe stream_deckx.py --headless", 0, False
