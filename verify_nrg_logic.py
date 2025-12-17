import os
import sys
# Force UTF-8 for console output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from processor import AudioProcessor, MountManager, DiscInspector

# Target File failing in Live Test
TARGET_NRG = r"D:\Music\VN\Audiophile VN\Phạm Duy - Duy Cường - Duy Quang Collection\Nhạc Phạm Duy (27CDs - Phương Nam Film)\PNF-Pham Duy Vol.2-Dua Em Tim Dong Hoa Vang [NRG]\Pham Duy Vol.2-Dua Em Tim Dong Hoa Vang.nrg"
OUTPUT_DIR = os.path.dirname(TARGET_NRG)

def test_logic():
    print(f"Testing Logic on: {TARGET_NRG}")
    if not os.path.exists(TARGET_NRG):
        print("CRITICAL: File not found!")
        return

    processor = AudioProcessor()
    
    # 1. Test Mount First
    print("--- Step 1: Attempt Direct Mount ---")
    drive = MountManager.mount(TARGET_NRG)
    print(f"Direct Mount Result: {drive}")
    
    if drive:
        print(f"--- Step 2: Inspect Drive {drive} ---")
        disc_type = DiscInspector.identify(drive)
        print(f"Disc Type: {disc_type}")
        
        print("--- Step 3: List Files in Drive ---")
        try:
           print(os.listdir(drive))
        except Exception as e:
           print(f"Listdir error: {e}")
           
        MountManager.unmount(TARGET_NRG)
    else:
        print("Direct Mount Failed.")
        
    # 2. Test Full Workflow
    print("\n--- Step 4: Run process_iso_workflow ---")
    try:
        # Note: ensuring we are calling the NEW method
        if not hasattr(processor, 'process_iso_workflow'):
             print("CRITICAL: AudioProcessor has no 'process_iso_workflow'. Check code update!")
        else:
             files = processor.process_iso_workflow(TARGET_NRG, OUTPUT_DIR)
             print(f"Workflow Result Files: {files}")
    except Exception as e:
        print(f"Workflow Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_logic()
