import os
import subprocess
import json
import re
import requests
import struct
import time
from mutagen import File
import mutagen.flac

class MountManager:
    @staticmethod
    def mount(iso_path):
        """
        Mounts ISO/Image and returns the Drive Letter (e.g. 'E:\\').
        Uses PowerShell. Attempts native mounting first.
        """
        iso_path = os.path.abspath(iso_path)
        print(f"Mounting: {iso_path}")
        
        # 1. Mount (Try without specifying StorageType first to let Windows decide)
        # BUG FIX: Use -LiteralPath instead of -ImagePath to handle square brackets [] and other wildcards in filenames
        cmd_mount = f'powershell -Command "Mount-DiskImage -LiteralPath \'{iso_path}\' -PassThru | Get-Volume | Select-Object -ExpandProperty DriveLetter"'
        try:
            res = subprocess.run(cmd_mount, capture_output=True, text=True, check=True)
            drive_letter = res.stdout.strip()
            if drive_letter:
                return f"{drive_letter}:\\"
        except subprocess.CalledProcessError as e:
            print(f"Mount failed (Native): {e}")
        
        return None

    @staticmethod
    def unmount(iso_path):
        iso_path = os.path.abspath(iso_path)
        # Verify path exists before unmounting to avoid PS errors? PowerShell handles it gracefully usually.
        print(f"Unmounting: {iso_path}")
        cmd_unmount = f'powershell -Command "Dismount-DiskImage -ImagePath \'{iso_path}\' -Confirm:$false"'
        subprocess.run(cmd_unmount, capture_output=True)

class DiscInspector:
    @staticmethod
    def identify(drive_path):
        """
        Scans drive to determine Disc Type.
        Returns: 'SACD', 'AUDIOCD', 'DATA', or 'UNKNOWN'
        """
        if not os.path.exists(drive_path):
            return "UNKNOWN"
            
        print(f"Inspecting Drive: {drive_path}")
        try:
            files = os.listdir(drive_path)
        except Exception:
            return "UNKNOWN"
            
        files_lower = [f.lower() for f in files]
        
        # Check for SACD structure
        if "2ch" in files_lower or "stereo" in files_lower or "master" in files_lower:
            return "SACD"
        
        # Check for .cda files (Audio CD)
        if any(f.endswith('.cda') for f in files_lower):
            return "AUDIOCD"
            
        # Recursive scan for SACD (sometimes inside a folder)
        for root, dirs, filenames in os.walk(drive_path):
            if any(f.endswith('.dsf') or f.endswith('.dff') for f in filenames):
                return "SACD"
            if "2ch" in [d.lower() for d in dirs]:
                return "SACD"
                
        return "DATA"

class AudioProcessor:
    def __init__(self):
        # Paths verification for Bundled App (PyInstaller) vs Dev Mode
        self.FFMPEG_PATH = self.get_resource_path("ffmpeg.exe")
        self.FPCALC_PATH = self.get_resource_path("fpcalc.exe")
        # sacd_extract is expected in the same location
        
        self.LOCAL_MB_SERVER = "http://127.0.0.1:5000"
        self.ACOUSTID_API_KEY = "cSpUJKpD"

    def get_resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        import sys
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            return os.path.join(sys._MEIPASS, relative_path)
        
        # Dev Mode: Hardcoded paths or relative
        # Backup: Look in ./bin folder relative to Main Script
        base_path = os.path.dirname(os.path.abspath(__file__))
        bin_dir = os.path.join(base_path, "bin")
        
        dev_map = {
            "ffmpeg.exe": os.path.join(bin_dir, "ffmpeg.exe"),
            "fpcalc.exe": os.path.join(bin_dir, "fpcalc.exe"),
            "sacd_extract.exe": os.path.join(bin_dir, "sacd_extract.exe")
        }
        return dev_map.get(relative_path, os.path.join(os.path.abspath("."), relative_path))

    def detect_silence(self, file_path, db_threshold=-40, min_duration=2.0):
        """
        Scans file for silence and returns a list of (start, end) timestamps for TRACKS (audio segments).
        """
        print(f"Scanning for silence in {file_path}...")
        command = [
            self.FFMPEG_PATH,
            "-i", file_path,
            "-af", f"silencedetect=noise={db_threshold}dB:d={min_duration}",
            "-f", "null",
            "-"
        ]
        
        try:
            result = subprocess.run(command, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=True)
            output = result.stderr
        except subprocess.CalledProcessError as e:
            print(f"Error running ffmpeg: {e}")
            return []

        # Parse ffmpeg output
        # [silencedetect @ ...] silence_start: 254.558
        # [silencedetect @ ...] silence_end: 257.062 | silence_duration: 2.50365
        
        silence_starts = []
        silence_ends = []
        
        for line in output.split('\n'):
            if "silence_start" in line:
                match = re.search(r"silence_start: (\d+(\.\d+)?)", line)
                if match:
                    silence_starts.append(float(match.group(1)))
            elif "silence_end" in line:
                match = re.search(r"silence_end: (\d+(\.\d+)?)", line)
                if match:
                    silence_ends.append(float(match.group(1)))

        # Logic: Audio is what happens BETWEEN silence_end of previous and silence_start of next.
        # First track starts at 0.0
        
        tracks = []
        current_start = 0.0
        
        # Zip silences to find breaks
        # We need to handle the case where silence_starts has one more item than ends (final silence) or vice versa
        
        # Simplified logic:
        # Track 1: 0.0 -> silence_starts[0]
        # Track 2: silence_ends[0] -> silence_starts[1]
        # ...
        
        # Sort just in case
        silence_starts.sort()
        silence_ends.sort()
        
        # Filter out silence at very beginning (if any)
        if silence_ends and silence_ends[0] < 1.0:
            current_start = silence_ends[0]
            silence_ends = silence_ends[1:]
            if silence_starts and silence_starts[0] < 1.0:
                 silence_starts = silence_starts[1:]

        count = min(len(silence_starts), len(silence_ends))
        
        for i in range(count):
            gap_start = silence_starts[i]
            gap_end = silence_ends[i]
            
            # Add track BEFORE this gap
            if gap_start > current_start:
                tracks.append((current_start, gap_start))
            
            # Next track starts after this gap
            current_start = gap_end
            
        # Add final track (from last silence end to file duration?)
        # We need file duration for this.
        blocks = self.get_duration(file_path)
        if blocks > current_start:
              tracks.append((current_start, blocks))
              
        return tracks

    def get_duration(self, file_path):
        cmd = [self.FFMPEG_PATH, "-i", file_path]
        res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
        # Duration: 00:04:32.45
        match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", res.stderr)
        if match:
            h, m, s = match.groups()
            return int(h)*3600 + int(m)*60 + float(s)
        return 0.0

    def split_file(self, file_path, tracks, output_dir):
        """
        Splits file into chunks.
        """
        print(f"Splitting {len(tracks)} tracks...")
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1]
        
        output_files = []
        
        for i, (start, end) in enumerate(tracks):
            track_num = i + 1
            out_name = f"{file_name} - Track {track_num:02d}{ext}"
            out_path = os.path.join(output_dir, out_name)
            
            # cmd = f'ffmpeg -i "{file_path}" -ss {start} -to {end} -c copy "{out_path}" -y'
            cmd = [
                self.FFMPEG_PATH, "-y",
                "-i", file_path,
                "-ss", str(start),
                "-to", str(end),
                "-c", "copy",
                out_path
            ]
            
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            output_files.append(out_path)
            print(f"Generated: {out_name}")
            
        return output_files

    def get_fingerprint(self, file_path):
        """
        Runs fpcalc and returns (duration, fingerprint)
        """
        cmd = [self.FPCALC_PATH, "-json", file_path]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, check=True, text=True, encoding='utf-8', errors='replace')
            data = json.loads(res.stdout)
            return data["duration"], data["fingerprint"]
        except Exception as e:
            print(f"Fingerprint error for {file_path}: {e}")
            return None, None

    def lookup_metadata(self, duration, fingerprint):
        """
        1. Query AcoustID to get MBID.
        2. Query Local MB Server for Metadata.
        """
        # Headers for "Good Citizen" API usage
        headers = {
            "User-Agent": "AutoSplitTagger/1.0 ( contact@antigravity.cool )"
        }
        
        # Step 1: AcoustID (Internet)
        acoustid_url = "https://api.acoustid.org/v2/lookup"
        params = {
            "client": self.ACOUSTID_API_KEY,
            "meta": "recordingids",
            "duration": int(duration),
            "fingerprint": fingerprint
        }
        
        try:
            r = requests.get(acoustid_url, params=params, headers=headers)
            data = r.json()
            if data['status'] != 'ok' or not data['results']:
                return None
            
            # Get first recording ID
            mb_recording_id = data['results'][0]['recordings'][0]['id']
            print(f"Found AcoustID match -> MBID: {mb_recording_id}")

            # Step 2: Local MusicBrainz Server (Local)
            # http://127.0.0.1:5000/ws/2/recording/MBID?inc=releases+artists&fmt=json
            mb_url = f"{self.LOCAL_MB_SERVER}/ws/2/recording/{mb_recording_id}"
            mb_params = {
                "inc": "releases+artists+media", 
                "fmt": "json"
            }
            
            r_mb = requests.get(mb_url, params=mb_params, headers=headers)
            mb_data = r_mb.json()
            
            # Extract basic tags
            title = mb_data.get('title', 'Unknown')
            artist = mb_data['artist-credit'][0]['artist']['name'] if 'artist-credit' in mb_data else 'Unknown'
            album = 'Unknown'
            if 'releases' in mb_data and mb_data['releases']:
                album = mb_data['releases'][0]['title']
            
            return {
                "title": title,
                "artist": artist,
                "album": album,
                "mbid": mb_recording_id
            }

        except Exception as e:
            print(f"Lookup error: {e}")
            return None

    def convert_nrg_to_iso(self, nrg_path, output_dir):
        """
        Parses NRG footer to find the data offset and extracts the ISO/BIN payload.
        Returns path to the extracted .iso file.
        """
        print(f"Converting NRG: {nrg_path}")
        try:
            with open(nrg_path, 'rb') as f:
                f.seek(0, 2)
                filesize = f.tell()
                
                # Check footer (Last 12 bytes)
                # NER5 footer: [4s tag][8b offset]
                f.seek(-12, 2)
                footer = f.read(12)
                tag = footer[:4]
                
                offset = 0
                if tag == b'NER5':
                    offset = struct.unpack('>Q', footer[4:])[0] # Big Endian Unsigned Long Long
                elif tag == b'NERO':
                    # NERO footer (older): often just offset
                    pass
                
                if offset > 0 and offset < filesize:
                    print(f"Found NER5 Footer. Data Limit: {offset}")
                else:
                    # Fallback
                    print("No valid NER5 footer. Assuming Raw Copy or Standard ISO inside.")
                    offset = filesize 

                # Extract
                # User Request: ISO/FLAC result must be in same folder as Source
                iso_name = os.path.splitext(os.path.basename(nrg_path))[0] + ".iso"
                iso_path = os.path.join(output_dir, iso_name)
                
                print(f"Saving Converted ISO to: {iso_path}")
                
                f.seek(0)
                with open(iso_path, 'wb') as out:
                    # Read in chunks
                    chunk_size = 1024 * 1024 # 1MB
                    remaining = offset
                    while remaining > 0:
                        to_read = min(chunk_size, remaining)
                        data = f.read(to_read)
                        if not data:
                            break
                        out.write(data)
                        remaining -= len(data)
                
                if os.path.exists(iso_path):
                     print(f"Conversion Success. Size: {os.path.getsize(iso_path)} bytes")
                else:
                     print("Conversion Failed: File not created.")
                        
            return iso_path
        except Exception as e:
            print(f"NRG Conversion Failed: {e}")
            return None

    def process_iso(self, file_path, output_dir):
        """
        Input can be .iso or .nrg
        1. If NRG -> Convert to ISO first.
        2. Extact ISO using sacd_extract.
        Returns: (flac_files, iso_path)
        """
        iso_path = file_path
        
        # NRG HANDLER
        if file_path.lower().endswith('.nrg'):
            iso_path = self.convert_nrg_to_iso(file_path, output_dir)
            if not iso_path:
                print("Failed to convert NRG.")
                return None, None
            
        print(f"Extracting ISO: {iso_path}")
        sacd_exe = self.get_resource_path("sacd_extract.exe")
        
        # 1. Extract to DSF (Sony format, supports tags)
        # sacd_extract -2 (stereo) -s (DSF) -c (convert DST) -i input.iso
        cmd_extract = [
            sacd_exe,
            "-2", "-s", "-c",
            "-i", iso_path
        ]
        
        # sacd_extract unfortunately outputs to the CURRENT WORKING DIRECTORY or specific folder logic
        # We should set CWD to output_dir for the subprocess
        try:
            subprocess.run(cmd_extract, cwd=output_dir, check=True, stdout=subprocess.DEVNULL)
        except Exception as e:
            print(f"sacd_extract failed: {e}")
            # Do not return yet, we might want to return None, iso_path to let caller know ISO is ready but extract failed
            return None, iso_path

        # 2. Find extracted .dsf files
        dsf_files = sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.casefold().endswith('.dsf')])
        flac_files = []

        # 3. Convert DSF to FLAC
        for dsf in dsf_files:
            flac_name = os.path.splitext(os.path.basename(dsf))[0] + ".flac"
            flac_path = os.path.join(output_dir, flac_name)
            
            print(f"Converting to FLAC: {flac_name}")
            cmd_conv = [
                self.FFMPEG_PATH, "-y",
                "-i", dsf,
                "-compression_level", "5",
                flac_path
            ]
            
            try:
                subprocess.run(cmd_conv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                flac_files.append(flac_path)
                # Cleanup DSF
                os.remove(dsf)
            except Exception as e:
                print(f"Failed to convert {dsf}: {e}")

        if not flac_files:
            return None, iso_path # Signal to main.py to fallback (but provide iso_path)

        return flac_files, iso_path

    # ... existing imports ...



    # ... unmount ...

    # ... DiscInspector ...

# ... AudioProcessor class ...

        return generated_files

    # --- NRG DIRECT EXTRACTION (NO MOUNT) ---
    def parse_nrg_structure(self, nrg_path):
        """
        Parses NER5 footer and CUEX chunk to get Track Offsets.
        Returns list of tuples: (start_sector, end_sector)
        """
        tracks = []
        try:
            with open(nrg_path, 'rb') as f:
                f.seek(0, 2)
                file_size = f.tell()
                f.seek(-12, 2)
                footer = f.read(12)
                
                if footer[:4] != b'NER5':
                    return []
                
                offset = struct.unpack('>Q', footer[4:])[0]
                f.seek(offset)
                
                while f.tell() < file_size:
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8: break
                    chunk_id, chunk_size = struct.unpack('>4sI', chunk_header)
                    
                    if chunk_id == b'END!': break
                    
                    if chunk_id == b'CUEX':
                        # Parse CUEX
                        data = f.read(chunk_size)
                        # Basic parsing logic derived from nrg_parser.py
                        # Each entry 8 bytes: [Mode][Index][Reserved][Sector (4b)]
                        entry_size = 8
                        num_entries = len(data) // entry_size
                        
                        current_track = 1
                        last_sector = 0
                        
                        # We collect Start Sectors for each Track (Index=1) -- Wait, byte 1 is Track No?
                        # Based on nrg_parser output:
                        # Entry 2: Index(Track?)=1, Sector=0
                        # Entry 3: Index(Track?)=2, Sector=28141
                        # Entry 19 (Last): Sector=222174
                        
                        # Let's collect all sector boundaries
                        boundaries = []
                        for i in range(num_entries):
                            entry = data[i*entry_size : (i+1)*entry_size]
                            # track_idx = entry[1]
                            sector = struct.unpack('>I', entry[4:])[0]
                            # Filter crazy large sectors (pre-gap)
                            if sector < 4000000000:
                                boundaries.append(sector)
                        
                        # Remove duplicates and sort
                        boundaries = sorted(list(set(boundaries)))
                        
                        # Form tracks: [Start, End]
                        # boundaries[0] -> boundaries[1] = Track 1
                        for i in range(len(boundaries) - 1):
                            start = boundaries[i]
                            end = boundaries[i+1]
                            if end > start:
                                tracks.append((start, end))
                                
                    else:
                        f.seek(chunk_size, 1)

        except Exception as e:
            print(f"NRG Parse Error: {e}")
            return []
            
        return tracks

    def extract_nrg_direct(self, nrg_path, output_dir):
        """
        Extracts Audio Tracks directly from NRG raw data using ffmpeg pipe.
        """
        print(f"Attempting Direct NRG Extraction (No Mount): {nrg_path}")
        tracks = self.parse_nrg_structure(nrg_path)
        if not tracks:
            print("No tracks found in NRG structure.")
            return []
            
        generated_files = []
        nrg_file_obj = open(nrg_path, 'rb') # Keep open
        
        try:
            for i, (start_sector, end_sector) in enumerate(tracks):
                track_num = i + 1
                track_len_sectors = end_sector - start_sector
                byte_offset = start_sector * 2352
                byte_len = track_len_sectors * 2352
                
                out_name = os.path.splitext(os.path.basename(nrg_path))[0] + f" - Track {track_num:02d}.flac"
                out_path = os.path.join(output_dir, out_name)
                
                print(f"Extracting T{track_num}: Offset {byte_offset}, Len {byte_len} bytes -> {out_name}")
                
                # Seek and Read
                nrg_file_obj.seek(byte_offset)
                # Read in chunks to pipe
                
                # FFMPEG Command: Read from Pipe, Format s16le, 44100, stereo
                cmd = [
                    self.FFMPEG_PATH, "-y",
                    "-f", "s16le", "-ar", "44100", "-ac", "2",
                    "-i", "pipe:0",
                    "-compression_level", "5",
                    out_path
                ]
                
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Feed data
                try:
                    # We can define a chunk size to avoid memory overflow for large tracks
                    # But Popen.communicate reads all at once if passed?
                    # Better: write to stdin in loop
                    
                    bytes_written = 0
                    chunk_size = 65536
                    while bytes_written < byte_len:
                        to_read = min(chunk_size, byte_len - bytes_written)
                        data = nrg_file_obj.read(to_read)
                        if not data: break
                        try:
                            proc.stdin.write(data)
                            bytes_written += len(data)
                        except BrokenPipeError:
                            break
                    
                    proc.stdin.close()
                    proc.wait()
                    
                    if proc.returncode == 0:
                        generated_files.append(out_path)
                    else:
                        print(f"FFmpeg Error for Track {track_num}")
                        
                except Exception as e:
                    print(f"Pipe Error: {e}")
                    proc.kill()
                    
        except Exception as e:
            print(f"Extraction Error: {e}")
        finally:
            nrg_file_obj.close()
            
        return generated_files

    # --- CUE / BIN SUPPORT ---
    def parse_cue(self, cue_path):
        """
        Parses .cue file to find the BIN file and Track Timestamps.
        Returns: (bin_filename, tracks_list)
                 tracks_list = [(start_sec, end_sec, track_num)]
        """
        tracks = []
        bin_file = None
        current_track_idx = 0
        current_index01 = 0.0
        
        try:
            with open(cue_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            for line in lines:
                parts = line.strip().split()
                if not parts: continue
                
                # FILE "Name.bin" BINARY
                if parts[0] == 'FILE':
                    # Extract filename between quotes
                    match = re.search(r'FILE "(.*)"', line)
                    if match:
                        bin_file = match.group(1)
                    else:
                        # Fallback simple split if regex fails (rare)
                        bin_file = " ".join(parts[1:-1]).strip('"')
                        
                # TRACK 01 AUDIO
                elif parts[0] == 'TRACK':
                    current_track_idx = int(parts[1])
                    
                # INDEX 01 00:00:00
                elif parts[0] == 'INDEX' and parts[1] == '01':
                    timestamp = parts[2] # MM:SS:FF
                    try:
                        m, s, f_res = map(int, timestamp.split(':'))
                        seconds = m*60 + s + f_res/75.0
                        
                        if current_track_idx > 1 and tracks:
                            # Close previous track
                            prev_start, _, prev_id = tracks[-1]
                            tracks[-1] = (prev_start, seconds, prev_id)
                            
                        # Start new track
                        tracks.append((seconds, None, current_track_idx)) # End is None for now
                    except ValueError:
                        pass # Ignore malformed index
            
            # Handle last track end? We leave it None.
            
        except Exception as e:
            print(f"CUE Parse Error: {e}")
            return None, []
            
        return bin_file, tracks

    def extract_cue_direct(self, cue_path, output_dir):
        print(f"Processing CUE Sheet: {cue_path}")
        bin_filename, tracks = self.parse_cue(cue_path)
        
        if not bin_filename or not tracks:
            print("Invalid CUE or no tracks found.")
            return []
            
        # Locate BIN file
        # Usually in same dir as CUE
        cue_dir = os.path.dirname(cue_path)
        bin_path = os.path.join(cue_dir, bin_filename)
        
        # If BIN not found, try replacing extension of CUE to BIN (common mismatch)
        if not os.path.exists(bin_path):
             alt_bin = os.path.splitext(cue_path)[0] + ".bin"
             if os.path.exists(alt_bin):
                 bin_path = alt_bin
             else:
                 print(f"BIN file not found: {bin_path}")
                 return []
            
        generated_files = []
        
        for i, (start, end, track_num) in enumerate(tracks):
            track_name = f"Track {track_num:02d}"
            output_path = os.path.join(output_dir, f"{track_name}.flac")
            
            # Formulate FFmpeg command
            # Input is Raw CDDA: -f s16le -ar 44100 -ac 2
            cmd = [
                self.FFMPEG_PATH, "-y",
                "-f", "s16le", "-ar", "44100", "-ac", "2",
                "-i", bin_path,
                "-ss", f"{start:.3f}"
            ]
            
            if end is not None:
                cmd.extend(["-to", f"{end:.3f}"])
                
            cmd.extend([output_path])
            
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                generated_files.append(output_path)
                print(f"Extracted: {track_name}")
            except Exception as e:
                print(f"Failed to extract Track {track_num}: {e}")
                
        return generated_files

    def process_iso_workflow(self, file_path, output_dir):
        """
        New Main Workflow for ISO/NRG/CUE.
        Returns list of generated files.
        """
        print(f"DEBUG: Entered process_iso_workflow with {file_path}")
        generated_files = []
        lower_path = file_path.lower()
        
        # 0. CUE SHEET Support
        if lower_path.endswith('.cue'):
             print("Detected CUE Sheet. Attempting Direct Bin Extraction...")
             return self.extract_cue_direct(file_path, output_dir)

        is_nrg = lower_path.endswith('.nrg')
    
    # 1. DIRECT NRG EXTRACTION (New Priority)
        if is_nrg:
            print("Detected NRG. Attempting Direct Parsing (No Mount)...")
            res = self.extract_nrg_direct(file_path, output_dir)
            if res:
                return res
            print("Direct Parsing failed. Falling back to Legacy Mount/Convert.")

        # ... Legacy Logic Below (Mounting) ...
        active_iso_path = file_path
        created_temp_iso = False

        # If it was NRG and Direct failed, we try Convert -> ISO
        if is_nrg:
             # ... existing convert logic ...
             iso_path = self.convert_nrg_to_iso(file_path, output_dir)
             if iso_path:
                active_iso_path = iso_path
                created_temp_iso = True
             else:
                return []
        
        # 2. Mount ISO
        drive = MountManager.mount(active_iso_path)
        # ... rest of existing function ...
        if not drive:
             # ...
             return self.extract_sacd_legacy(active_iso_path, output_dir)

        disc_type = DiscInspector.identify(drive)
        # ...
        if disc_type == "SACD":
             MountManager.unmount(active_iso_path)
             return self.extract_sacd_legacy(active_iso_path, output_dir)
        elif disc_type == "AUDIOCD":
             res = self.rip_audio_cd(drive, output_dir)
             MountManager.unmount(active_iso_path)
             return res
        else:
             MountManager.unmount(active_iso_path)
        
        # Cleanup
        if created_temp_iso and os.path.exists(active_iso_path):
             try: os.remove(active_iso_path)
             except: pass
             
        return generated_files

    def rip_audio_cd(self, drive_path, output_dir):
        """
        Rips .cda files from the mounted Audio CD to FLAC.
        """
        print(f"Ripping Audio CD from {drive_path}...")
        try:
            files = [f for f in os.listdir(drive_path) if f.lower().endswith('.cda')]
            # Sort by track number (Track01.cda, Track02.cda...)
            files.sort()
            
            generated_files = []
            for cda_file in files:
                track_name = os.path.splitext(cda_file)[0]
                input_path = os.path.join(drive_path, cda_file)
                output_path = os.path.join(output_dir, f"{track_name}.flac")
                
                print(f"Ripping {cda_file} -> {output_path}")
                # ffmpeg can read .cda on Windows if paths are correct
                cmd = [self.FFMPEG_PATH, "-y", "-i", input_path, "-compression_level", "5", output_path]
                
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    generated_files.append(output_path)
                except subprocess.CalledProcessError as e:
                    print(f"Failed to rip {cda_file}: {e}")
                    
            return generated_files
        except Exception as e:
            print(f"Error accessing Audio CD drive: {e}")
            return []

    def extract_sacd_legacy(self, iso_path, output_dir):
        # ... logic moved from old process_iso ...
        sacd_exe = self.get_resource_path("sacd_extract.exe")
        cmd_extract = [sacd_exe, "-2", "-s", "-c", "-i", iso_path]
        try:
            subprocess.run(cmd_extract, cwd=output_dir, check=True, stdout=subprocess.DEVNULL)
            # Find DSF and convert to FLAC (existing logic)
            dsf_files = sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.casefold().endswith('.dsf')])
            flac_files = []
            for dsf in dsf_files:
                flac_name = os.path.splitext(os.path.basename(dsf))[0] + ".flac"
                flac_path = os.path.join(output_dir, flac_name)
                # Ensure FFMPEG_PATH is available
                subprocess.run([self.FFMPEG_PATH, "-y", "-i", dsf, "-compression_level", "5", flac_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                flac_files.append(flac_path)
                os.remove(dsf)
            return flac_files
        except Exception as e:
            print(f"SACD Extract Error: {e}")
            return []

    def tag_file(self, file_path, metadata):
        """
        Applies tags using Mutagen.
        Supports FLAC, MP3, OGG, etc. automatically via mutagen.File
        """
        try:
            audio = File(file_path, easy=True)
            
            if audio is None:
                # Fallback for fresh FLACs from ffmpeg sometimes needed
                try:
                    audio = mutagen.flac.FLAC(file_path)
                except:
                    print(f"Mutagen could not handle: {file_path}")
                    return

            if metadata.get('title'):
                audio['title'] = metadata['title']
            if metadata.get('artist'):
                audio['artist'] = metadata['artist']
            if metadata.get('album'):
                audio['album'] = metadata['album']
            
            # Save tags
            audio.save()
            print(f"Tagged: {file_path}")
            
        except ImportError:
            print("Mutagen not installed. Skipping tags.")
        except Exception as e:
            print(f"Error tagging {file_path}: {e}")
