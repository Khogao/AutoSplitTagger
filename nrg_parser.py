import struct
import os
import sys

# Force UTF-8 for console output
sys.stdout.reconfigure(encoding='utf-8')

# Path to the specific file user is testing
TARGET_NRG = r"D:\Music\VN\Audiophile VN\Phạm Duy - Duy Cường - Duy Quang Collection\Nhạc Phạm Duy (27CDs - Phương Nam Film)\PNF-Pham Duy Vol.2-Dua Em Tim Dong Hoa Vang [NRG]\Pham Duy Vol.2-Dua Em Tim Dong Hoa Vang.nrg"

def parse_nrg(file_path):
    print(f"Parsing: {file_path}")
    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, 'rb') as f:
        f.seek(0, 2)
        total_size = f.tell()
        
        # 1. Read Footer (Last 12 bytes)
        f.seek(-12, 2)
        footer_data = f.read(12)
        
        if len(footer_data) < 12:
            print("File too small.")
            return

        tag = footer_data[:4]
        print(f"Footer Tag: {tag}")
        
        if tag == b'NER5':
            offset = struct.unpack('>Q', footer_data[4:])[0]
            print(f"Chain Offset: {offset}")
            
            # Jump to Chain
            f.seek(offset)
            
            # Read Chunks
            while True:
                if f.tell() >= total_size:
                    break
                    
                chunk_header = f.read(8)
                if len(chunk_header) < 8:
                    break
                    
                chunk_id, chunk_size = struct.unpack('>4sI', chunk_header)
                print(f"Chunk: {chunk_id}, Size: {chunk_size}")
                
                # Check for END chunk
                if chunk_id == b'END!':
                    break
                
                # Parse CUEX if found
                if chunk_id == b'CUEX':
                    parse_cuex(f.read(chunk_size))
                elif chunk_id == b'DAOX':
                    # DAOX is complex, often larger
                    print("Found DAOX (Disc At Once Info).")
                    f.seek(chunk_size, 1) # Skip payload for now
                else:
                    f.seek(chunk_size, 1) # Skip payload

        else:
             print("Not a NER5 NRG file.")

def parse_cuex(data):
    print("--- CUEX Content ---")
    # CUEX structure: 
    # Usually blocks of 8 bytes? Or text?
    # Ner5 CUEX is binary.
    # Format: [Track Mode 1b][Index 1b][Reserved 2b][Sector 4b (Big Endian)]
    
    # Check size
    entry_size = 8
    num_entries = len(data) // entry_size
    print(f"Entries: {num_entries}")
    
    for i in range(num_entries):
        entry = data[i*entry_size : (i+1)*entry_size]
        mode = entry[0] # 0x41 for Audio?
        index = entry[1]
        sector = struct.unpack('>I', entry[4:])[0]
        print(f"  Entry {i}: Mode={hex(mode)}, Index={index}, Sector={sector}, ByteOffset={sector*2352}")

if __name__ == "__main__":
    parse_nrg(TARGET_NRG)
