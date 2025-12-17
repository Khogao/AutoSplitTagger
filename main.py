import sys
import os
import threading
# Force UTF-8 encoding (Fix for Vietnamese characters crash in CLI)
if sys.platform.startswith('win'):
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding='utf-8')
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QPushButton, QListWidget, QProgressBar, 
                             QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from processor import AudioProcessor

class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    success = pyqtSignal(str)

class AutoSplitTagger(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Antigravity AutoSplitTagger")
        self.setGeometry(100, 100, 600, 500)
        self.setAcceptDrops(True)

        self.processor = AudioProcessor()
        self.file_queue = [] # Queue for batch processing

        # UI Setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # header
        self.lbl_status = QLabel("Drag & Drop Compilation ISO/NRG/FLAC files here")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(self.lbl_status)

        # list
        self.list_tracks = QListWidget()
        layout.addWidget(self.list_tracks)

        # progress
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # layout controls
        controls_layout = QVBoxLayout()
        
        self.lbl_db = QLabel("Silence Threshold (dB):")
        self.spin_db = QSpinBox()
        self.spin_db.setRange(-100, 0)
        self.spin_db.setValue(-25)
        self.spin_db.setToolTip("Lower = Stricter silence. Higher = Accepts noisy silence.")
        controls_layout.addWidget(self.lbl_db)
        controls_layout.addWidget(self.spin_db)
        
        self.lbl_dur = QLabel("Min Silence Duration (s):")
        self.spin_dur = QDoubleSpinBox()
        self.spin_dur.setRange(0.1, 10.0)
        self.spin_dur.setValue(0.5) 
        self.spin_dur.setSingleStep(0.1)
        controls_layout.addWidget(self.lbl_dur)
        controls_layout.addWidget(self.spin_dur)
        
        # Browse Button (Fallback for D&D)
        self.btn_browse = QPushButton("Browse Files...")
        self.btn_browse.clicked.connect(self.browse_file)
        layout.addWidget(self.btn_browse)

        layout.addLayout(controls_layout)

        # buttons
        self.btn_process = QPushButton("START BATCH PROCESSING")
        self.btn_process.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.start_processing)
        layout.addWidget(self.btn_process)

        self.signals = WorkerSignals()
        self.signals.progress.connect(self.update_log)
        self.signals.finished.connect(self.on_process_finished)
        self.signals.error.connect(self.show_error)
        self.signals.success.connect(self.show_success)

        # CLI / Auto-Run Check
        self.auto_exit = False
        if len(sys.argv) > 1:
            potential_file = sys.argv[1]
            if os.path.exists(potential_file):
                print(f"CLI Mode: Auto-processing {potential_file}")
                self.file_queue = [potential_file]
                self.list_tracks.addItem(f"Loaded via CLI: {potential_file}")
                self.auto_exit = True 
                self.start_processing()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.file_queue.extend(files) # Append all dropped files
            self.lbl_status.setText(f"Selected {len(self.file_queue)} files")
            self.list_tracks.addItem(f"Added {len(files)} files to queue.")
            self.btn_process.setEnabled(True)

    def update_log(self, message):
        self.list_tracks.addItem(message)
        self.list_tracks.scrollToBottom()

    def browse_file(self):
        fnames, _ = QFileDialog.getOpenFileNames(self, "Select Audio Files", "", "All Audio (*.flac *.wav *.iso *.nrg);;All Files (*)")
        if fnames:
            self.file_queue.extend(fnames)
            self.lbl_status.setText(f"Selected {len(self.file_queue)} files")
            self.list_tracks.addItem(f"Added {len(fnames)} files to queue.")
            self.btn_process.setEnabled(True)

    def log_debug(self, msg):
        try:
            with open("debug_log.txt", "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except:
            pass
        print(msg)

    def show_error(self, message):
        self.log_debug(f"ERROR: {message}")
        if self.auto_exit:
            self.lbl_status.setText(f"ERROR: {message}")
            self.list_tracks.addItem(f"CRITICAL ERROR: {message}")
            # Do NOT quit. Let user read it.
        else:
            QMessageBox.critical(self, "Error", message)
            self.btn_process.setEnabled(True)

    def show_success(self, message):
        self.log_debug(f"SUCCESS: {message}")
        if self.auto_exit:
            self.lbl_status.setText("DONE (Check Log)")
            QApplication.quit()
        else:
            QMessageBox.information(self, "Success", message)
            self.btn_process.setEnabled(True)

    def on_process_finished(self):
        self.list_tracks.addItem("=== BATCH DONE ===")
        self.progress_bar.setValue(100)
        pass # Handle auto-exit in show_success

    def start_processing(self):
        if not self.file_queue:
            return
        
        self.btn_process.setEnabled(False)
        self.progress_bar.setValue(0)
        
        db = self.spin_db.value()
        dur = self.spin_dur.value()
        
        # Clone queue to avoid threading issues if modified? (Though we process sequentially)
        queue_copy = list(self.file_queue)
        threading.Thread(target=self.run_logic, args=(queue_copy, db, dur), daemon=True).start()

    def run_logic(self, queue, db, dur):
        try:
            import processor
            self.processor = processor.AudioProcessor()
            
            output_dir = "" # Will be set in loop
            total_files_generated = 0
            
            for index, file_path in enumerate(queue):
                self.signals.progress.emit(f"--- Processing File {index+1}/{len(queue)}: {os.path.basename(file_path)} ---")
                
                output_dir = os.path.dirname(file_path)
                split_files = []
                
                # Check extension
                is_iso_container = file_path.lower().endswith('.iso') or file_path.lower().endswith('.nrg')
                
                fallback_needed = False
                
                # BRANCH: ISO/NRG
                if is_iso_container:
                    self.signals.progress.emit("DETECTED DISC IMAGE (ISO/NRG): Processing...")
                    
                # New Universal Workflow: Mount -> Inspect -> Act
                    split_files = self.processor.process_iso_workflow(file_path, output_dir)
                    
                    if not split_files:
                         self.signals.progress.emit("Warning: No audio files extracted from Disc Image.")

                else:
                    # Standard Audio File (FLAC, WAV, etc.)
                    self.signals.progress.emit(f"Step 1: Detecting Silence on {os.path.basename(file_path)}...")
                    tracks = self.processor.detect_silence(file_path, db_threshold=db, min_duration=dur)
                    
                    if not tracks:
                        self.signals.progress.emit(f"Warning: No silence detected on {os.path.basename(file_path)}. Skipping.")
                    else:
                        self.signals.progress.emit(f"Silence Detected. Splitting into {len(tracks)} tracks...")
                        split_files = self.processor.split_file(file_path, tracks, output_dir)

                # COMMON: Fingerprint & Tag (Result from either ISO Workflow or Standard Split)
                if split_files:
                    self.signals.progress.emit(f"Generated {len(split_files)} files. Starting Fingerprinting...")
                    total_files_generated += len(split_files)
                    for i, fpath in enumerate(split_files):
                         # ... (Tagging logic same as before, simplified for brevity in this replace)
                         self.signals.progress.emit(f"Processing Track {i+1}: {os.path.basename(fpath)}")
                         dur_val, fp = self.processor.get_fingerprint(fpath)
                         if dur_val and fp:
                             meta = self.processor.lookup_metadata(dur_val, fp)
                             if meta:
                                 self.signals.progress.emit(f"  > Tagged: {meta['title']}")
                                 self.processor.tag_file(fpath, meta)
                             else:
                                 self.signals.progress.emit("  > No Metadata found.")
                
            if total_files_generated == 0:
                if total_files_generated == 0:
                    self.signals.error.emit("Finished with NO output.\n[ISO/NRG]: Mount Failed? (Run as Admin)\n[Audio]: Silence Check Failed? (Adjust Threshold)")
            else:
                self.signals.success.emit(f"Batch Processing Complete! Generated {total_files_generated} files.")
            self.signals.finished.emit()

        except Exception as e:
            self.signals.error.emit(str(e))

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        # Global Exception Hook
        sys.excepthook = lambda cls, exception, traceback: open("crash_log.txt", "a").write(f"UNCAUGHT: {exception}\n")
        
        window = AutoSplitTagger()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        with open("crash_log.txt", "a") as f:
            f.write(f"CRITICAL STARTUP ERROR: {e}\n")
        print(f"CRITICAL: {e}")
