# build_and_test.ps1
# Automates the entire Build -> Test cycle to minimize User Interaction.

$ErrorActionPreference = "Stop"
$workDir = "d:\Work\Antigravity\references\AutoSplitTagger"
$nrgFile = "D:\Music\VN\Audiophile VN\Phạm Duy - Duy Cường - Duy Quang Collection\Nhạc Phạm Duy (27CDs - Phương Nam Film)\PNF-Văn Cao&Phạm Duy - Cung Dan Xua [NRG]\Cung Dan Xua 1.nrg"

Set-Location $workDir

Write-Host "[1/5] Killing old processes..." -ForegroundColor Cyan
Stop-Process -Name "AutoSplitTagger" -ErrorAction SilentlyContinue

Write-Host "[2/5] Cleaning build artifacts..." -ForegroundColor Cyan
Remove-Item -Path "dist", "build", "*.spec" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "[3/5] Building Executable with PyInstaller..." -ForegroundColor Cyan
# Run PyInstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "AutoSplitTagger" `
    --add-binary "D:\Work\Antigravity\references\resources\ffmpeg.exe;." `
    --add-binary "D:\Work\Antigravity\references\fpcalc.exe;." `
    --add-binary "D:\Work\Antigravity\references\sacd_extract.exe;." `
    main.py

if (-not (Test-Path "dist\AutoSplitTagger.exe")) {
    Write-Error "Build Failed! Exe not found."
    exit 1
}

Write-Host "[4/5] Running Live Test against NRG..." -ForegroundColor Cyan
Write-Host "Target: $nrgFile"

# Delete old logs to ensure fresh read
if (Test-Path "debug_log.txt") { Remove-Item "debug_log.txt" }

# Run the App in CLI mode -> wait for it to finish
Start-Process -FilePath "dist\AutoSplitTagger.exe" -ArgumentList "`"$nrgFile`"" -Wait -NoNewWindow

Write-Host "[5/5] Test Results (debug_log.txt):" -ForegroundColor Cyan
if (Test-Path "debug_log.txt") {
    Get-Content "debug_log.txt"
}
else {
    Write-Warning "Log file not found. Crashing?"
    if (Test-Path "crash_log.txt") {
        Write-Host "Found Crash Log:" -ForegroundColor Red
        Get-Content "crash_log.txt"
    }
    else {
        # Check dist location too (sometimes CWD varies)
        if (Test-Path "dist\crash_log.txt") { Get-Content "dist\crash_log.txt" }
    }
}

Write-Host "Workflow Complete." -ForegroundColor Green
