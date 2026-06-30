# Update Next Gen Agent in place: git pull (fast-forward only) + reinstall
# dependencies if requirements.txt changed. Refuses to run over uncommitted
# local changes (commit or stash them first).
$ErrorActionPreference = "Stop"

$dirty = git status --porcelain
if ($dirty) {
    Write-Host "Uncommitted local changes detected. Commit or stash before updating:"
    Write-Host $dirty
    exit 1
}

$before = git rev-parse HEAD
git fetch
git pull --ff-only
$after = git rev-parse HEAD

if ($before -eq $after) {
    Write-Host "Already up to date ($before)."
    exit 0
}

Write-Host "Updated $before -> $after"

$changedFiles = git diff --name-only $before $after -- requirements.txt
if ($changedFiles) {
    Write-Host "requirements.txt changed — reinstalling dependencies..."
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host "Update complete."
