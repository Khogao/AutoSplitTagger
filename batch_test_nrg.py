import os
import subprocess
import time

# Đường dẫn đến EXE đã build
EXE_PATH = r"d:\Work\Antigravity\references\AutoSplitTagger\dist\AutoSplitTagger.exe"
WORK_DIR = r"d:\Work\Antigravity\references\AutoSplitTagger"

# Danh sách 10 file NRG mẫu (Lấy từ kết quả tìm kiếm trước đó)
NRG_FILES = [
    r"D:\Music\VN\Audiophile VN\Xuân Hiếu Collection\Xuan Hieu - My Story\Mystory-Saxophonexuanhieu.nrg",
    r"D:\Music\VN\1. Nhac hai ngoai\Trung tâm Ca dao\CDCD121 - Lam Gia Minh-Nguoi Ve Don Vi Moi [Flac]\CDCD121-NguoiVeDonViMoi-LamGiaMinh.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\Tuan Ngoc Productions - Tuan Ngoc-Tam Su Gui Ve Dau [NRG]\Tuan Ngoc-Tam Su Gui Ve Dau.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\Tuan Ngoc Productions - Tuan Ngoc - Du Nghin Nam Qua Di (2000)\Du Nghin Nam Qua Di.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\Tuan Ngoc Productions - Giot Le Cho Ngan Sau [NRG]\Tuan Ngoc-Giot Le Cho Ngan Sau.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\PNF-Pham Duy -Truong Ca Han Mac Tu [NRG]\Pham Duy -Truong Ca Han Mac Tu.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\Nhã Ca CD021 - Ý Lan & Tuấn Ngọc - Dốc Mơ (NRG)\DocMo.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\Nhac Viet Collection - Tuan Ngoc - Nua Hon Thuong Dau\NhacVietCD-NuaHonThuongDau-TuanNgoc.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\Nhac Viet Collection - Tuan Ngoc - Goi Giac Mo Xua\NhacVietCD-GoiGiacMoXua-TuanNgoc.nrg",
    r"D:\Music\VN\Audiophile VN\Tuấn Ngọc\Tuấn Ngọc Collection (53CDs)\Nhac Viet Collection - Tuan Ngoc - Em Oi Ha Noi Pho\NhacVietCD-EmOiHaNoiPho-TuanNgoc.nrg"
]

def run_batch_test():
    print("=== BATCH TESTING AUTOSPLITTAGGER (10 FILES) ===")
    
    # Xây dựng command line arguments
    # AutoSplitTagger.exe file1 file2 file3 ...
    # Chế độ CLI sẽ tự động nhận diện và xử lý.
    
    # Lưu ý: Cần escape đường dẫn có khoảng trắng
    quoted_files = [f'"{f}"' for f in NRG_FILES]
    files_arg = " ".join(quoted_files)
    
    cmd = f'"{EXE_PATH}" {files_arg}'
    
    print(f"Executing: {cmd}")
    print("-" * 50)
    
    try:
        # Chạy EXE và capture output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=WORK_DIR,
            shell=True # Shell=True cần thiết cho việc parse arguments string dài
        )
        
        # Read output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                
        rc = process.poll()
        print("-" * 50)
        print(f"Batch Test Completed. Return Code: {rc}")
        
        if rc == 0:
            print("SUCCESS: All files processed successfully (or graceful skip).")
        else:
            print("FAILURE: Process returned error code.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if not os.path.exists(EXE_PATH):
        print(f"Error: Executable not found at {EXE_PATH}")
    else:
        run_batch_test()
