# Beendet den im Hintergrund laufenden Trading-Journal-Server (Schnellstart.ps1).
Add-Type -AssemblyName System.Windows.Forms

$prozesse = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -match "uvicorn api\.app:app" }

foreach ($p in $prozesse) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

$text = if ($prozesse) { "Trading-Journal beendet." } else { "Trading-Journal lief nicht." }
[System.Windows.Forms.MessageBox]::Show($text, "Trading-Journal") | Out-Null
