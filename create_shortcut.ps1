$ws = New-Object -ComObject WScript.Shell
$desktop = $ws.SpecialFolders("Desktop")
$shortcutPath = Join-Path $desktop "Claude Permissions.lnk"

$s = $ws.CreateShortcut($shortcutPath)

# Find pythonw.exe
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $python = (Get-Command python.exe).Source
    $pythonw = $python -replace 'python\.exe$', 'pythonw.exe'
}

$s.TargetPath = $pythonw
$s.Arguments = '"C:\Users\ritch\.claude\downloads\Claude-allow-all-toggle\AutoYesToggle.pyw"'
$s.WorkingDirectory = 'C:\Users\ritch\.claude\downloads\Claude-allow-all-toggle'
$s.Description = 'Claude Code Permissions Toggle'
$s.Save()

Write-Host "Shortcut created at: $shortcutPath"
Write-Host "Target: $pythonw"
