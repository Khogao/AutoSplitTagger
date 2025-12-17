# build_and_test.py
import os
import sys
import shutil
import subprocess
import time

# Force UTF-8 for stdout/stderr
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

WORK_DIR = r"d:\Work\Antigravity\references\AutoSplitTagger"
NRG_FILE = r"D:\Music\VN\Audiophile VN\Phạm Duy - Duy Cường - Duy Quang Collection\Nhạc Phạm Duy (27CDs - Phương Nam Film)\PNF-Pham Duy Vol.2-Dua Em Tim Dong Hoa Vang [NRG]\Pham Duy Vol.2-Dua Em Tim Dong Hoa Vang.nrg"

os.chdir(WORK_DIR)

def run_step(step_name, func):
    print(f"\n[STEP] {step_name}...", flush=True)
    try:
        func()
        print("-> OK", flush=True)
    except Exception as e:
        print(f"-> FAILED: {e}", flush=True)
        sys.exit(1)

def kill_process():
    # Best effort
    os.system('taskkill /F /IM "AutoSplitTagger.exe" >nul 2>&1')

def clean():
    for p in ["dist", "build"]:
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
    if os.path.exists("AutoSplitTagger.spec"):
        os.remove("AutoSplitTagger.spec")

def build():
    # PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--windowed",
        "--name", "AutoSplitTagger",
        "--add-binary", r"D:\Work\Antigravity\references\resources\ffmpeg.exe;.",
        "--add-binary", r"D:\Work\Antigravity\references\fpcalc.exe;.",
        "--add-binary", r"D:\Work\Antigravity\references\sacd_extract.exe;.",
        "main.py"
    ]
    subprocess.check_call(cmd)

def test():
    exe_path = os.path.join("dist", "AutoSplitTagger.exe")
    if not os.path.exists(exe_path):
        raise FileNotFoundError("EXE not found after build")
    
    print(f"Targeting File: {NRG_FILE}", flush=True)
    
    # Remove logs
    if os.path.exists("debug_log.txt"): os.remove("debug_log.txt")
    if os.path.exists("crash_log.txt"): os.remove("crash_log.txt")

    # Run EXE
    # We pass the NRG file as an argument
    subprocess.run([exe_path, NRG_FILE], check=False)
    
    # Check Logs
    print("\n--- debug_log.txt ---")
    if os.path.exists("debug_log.txt"):
        with open("debug_log.txt", "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("(debug_log.txt not found)")

    print("\n--- crash_log.txt ---")
    if os.path.exists("crash_log.txt"):
        with open("crash_log.txt", "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("(crash_log.txt not found)")

if __name__ == "__main__":
    run_step("Killing Old Processes", kill_process)
    run_step("Cleaning Artifacts", clean)
    run_step("Building EXE", build)
    run_step("Running Live Test", test)
