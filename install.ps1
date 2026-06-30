# Install Next Gen Agent from a git checkout: venv + dependencies.
# Run this once, inside an already-cloned repository.
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Installed. Run with:  .\.venv\Scripts\python.exe src\main.py"
