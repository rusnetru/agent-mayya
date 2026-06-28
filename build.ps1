# Build a standalone Windows executable for Next Gen Agent.
$ErrorActionPreference = "Stop"

pyinstaller --noconfirm --onefile --name next-gen-agent src/main.py

Write-Host "Build complete: dist\next-gen-agent.exe"
