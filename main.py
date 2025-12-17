import sys
import os
import threading
# Force UTF-8 encoding (Fix for Vietnamese characters crash in CLI)
if sys.platform.startswith('win'):
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding='utf-8')

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QLabel, QPushButton, QListWidget, QProgressBar, QTableWidget, QTableWidgetItem,
                             QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox, QLineEdit, QHeaderView)
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
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)

        self.processor = AudioProcessor()
        self.file_queue = []
        self.married_folders = []

        # UI Setup with Tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Single File Processing
        self.tab_single = QWidget()
        self.setup_single_tab()
        self.tabs.addTab(self.tab_single, "Single File")

        # Tab 2: Batch Processing
        self.tab_batch = QWidget()
        self.setup_batch_tab()
        self.tabs.addTab(self.tab_batch, "Batch Processing")

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

    def setup_single_tab(self):
        """Setup Single File Processing Tab"""
        layout = QVBoxLayout(self.tab_single)

        # header
        self.lbl_status = QLabel("Drag & Drop Compilation ISO/NRG/CUE/FLAC files here")
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
        
        # Browse Button
        self.btn_browse = QPushButton("Browse Files...")
        self.btn_browse.clicked.connect(self.browse_files)
        layout.addWidget(self.btn_browse)

        layout.addLayout(controls_layout)

        # Process button
        self.btn_process = QPushButton("START BATCH PROCESSING")
        self.btn_process.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.start_processing)
        layout.addWidget(self.btn_process)

    def setup_batch_tab(self):
        """Setup Batch Processing Tab"""
        layout = QVBoxLayout(self.tab_batch)

        # Header
        lbl_batch_header = QLabel("Batch Process Married Folders (CUE/BIN not yet split)")
        lbl_batch_header.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(lbl_batch_header)

        # Folder selection
        folder_layout = QHBoxLayout()
        self.txt_scan_folder = QLineEdit()
        self.txt_scan_folder.setPlaceholderText("Select folder to scan...")
        self.txt_scan_folder.setText("d:/music")  # Default
        folder_layout.addWidget(self.txt_scan_folder)
        
        self.btn_browse_folder = QPushButton("Browse...")
        self.btn_browse_folder.clicked.connect(self.browse_scan_folder)
        folder_layout.addWidget(self.btn_browse_folder)
        
        self.btn_scan = QPushButton("Scan")
        self.btn_scan.setStyleSheet("background-color: #2196F3; color: white; padding: 5px;")
        self.btn_scan.clicked.connect(self.scan_library)
        folder_layout.addWidget(self.btn_scan)
        
        layout.addLayout(folder_layout)

        # Results table
        self.table_married = QTableWidget()
        self.table_married.setColumnCount(4)
        self.table_married.setHorizontalHeaderLabels(["Folder", "CUE Files", "Source Files", "Status"])
        self.table_married.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_married)

        # Stats
        self.lbl_stats = QLabel("Ready to scan...")
        layout.addWidget(self.lbl_stats)

        # Batch progress
        self.batch_progress = QProgressBar()
        layout.addWidget(self.batch_progress)

        # Process button
        self.btn_process_batch = QPushButton("Process All Married Folders")
        self.btn_process_batch.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
        self.btn_process_batch.setEnabled(False)
        self.btn_process_batch.clicked.connect(self.start_batch_processing)
        layout.addWidget(self.btn_process_batch)

    def browse_scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Library Folder")
        if folder:
            self.txt_scan_folder.setText(folder)

    def scan_library(self):
        """Scan library for married folders"""
        root_path = self.txt_scan_folder.text()
        if not os.path.exists(root_path):
            QMessageBox.warning(self, "Error", "Folder does not exist!")
            return

        self.lbl_stats.setText("Scanning...")
        self.married_folders = []
        
        # Scan logic (from scan_library.py)
        for root, dirs, files in os.walk(root_path):
            cue_files = [f for f in files if f.lower().endswith('.cue')]
            if not cue_files:
                continue
                
            audio_exts = {'.flac', '.wav', '.mp3', '.m4a', '.ape', '.wv', '.dsf', '.dff'}
            source_files = []
            track_files = []
            
            for f in files:
                lower = f.lower()
                ext = os.path.splitext(lower)[1]
                if lower.endswith(('.bin', '.iso', '.nrg', '.img')):
                    source_files.append(f)
                    continue
                if ext in audio_exts:
                    try:
                        if os.path.getsize(os.path.join(root, f)) > 100 * 1024 * 1024:
                            source_files.append(f)
                        else:
                            track_files.append(f)
                    except:
                        pass
            
            # Married = Has Source, No Tracks
            if source_files and not track_files:
                self.married_folders.append({
                    'path': root,
                    'cue': cue_files[0],
                    'cue_count': len(cue_files),
                    'source_count': len(source_files)
                })

        # Update table
        self.table_married.setRowCount(len(self.married_folders))
        for i, folder in enumerate(self.married_folders):
            self.table_married.setItem(i, 0, QTableWidgetItem(os.path.relpath(folder['path'], root_path)))
            self.table_married.setItem(i, 1, QTableWidgetItem(str(folder['cue_count'])))
            self.table_married.setItem(i, 2, QTableWidgetItem(str(folder['source_count'])))
            self.table_married.setItem(i, 3, QTableWidgetItem("Pending"))

        self.lbl_stats.setText(f"Found {len(self.married_folders)} married folders ready to process")
        self.btn_process_batch.setEnabled(len(self.married_folders) > 0)

    def start_batch_processing(self):
        """Process all married folders"""
        if not self.married_folders:
            return

        self.btn_process_batch.setEnabled(False)
        self.batch_progress.setMaximum(len(self.married_folders))
        self.batch_progress.setValue(0)

        def batch_worker():
            for i, folder in enumerate(self.married_folders):
                cue_path = os.path.join(folder['path'], folder['cue'])
                self.signals.progress.emit(f"Processing {i+1}/{len(self.married_folders)}: {folder['path']}")
                
                try:
                    result = self.processor.process_iso_workflow(cue_path, folder['path'])
                    if result:
                        self.table_married.setItem(i, 3, QTableWidgetItem(f"✓ {len(result)} files"))
                    else:
                        self.table_married.setItem(i, 3, QTableWidgetItem("✗ Failed"))
                except Exception as e:
                    self.table_married.setItem(i, 3, QTableWidgetItem(f"✗ Error: {str(e)[:20]}"))
                
                self.batch_progress.setValue(i + 1)

            self.signals.success.emit(f"Batch processing complete! Processed {len(self.married_folders)} folders.")
            self.signals.finished.emit()

        thread = threading.Thread(target=batch_worker, daemon=True)
        thread.start()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path not in self.file_queue:
                self.file_queue.append(file_path)
                self.list_tracks.addItem(f"Queued: {os.path.basename(file_path)}")
        self.btn_process.setEnabled(len(self.file_queue) > 0)

    def update_log(self, message):
        self.list_tracks.addItem(message)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", 
            "All Supported (*.iso *.nrg *.cue *.bin *.flac *.wav *.mp3 *.m4a);;ISO Files (*.iso);;NRG Files (*.nrg);;CUE Files (*.cue);;Audio Files (*.flac *.wav *.mp3 *.m4a)"
        )
        for file_path in files:
            if file_path not in self.file_queue:
                self.file_queue.append(file_path)
                self.list_tracks.addItem(f"Queued: {os.path.basename(file_path)}")
        self.btn_process.setEnabled(len(self.file_queue) > 0)

    def log_debug(self, msg):
        try:
            with open("debug_log.txt", "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except:
            pass

    def show_error(self, message):
        self.lbl_status.setText("❌ Error")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
        QMessageBox.critical(self, "Error", message)
        self.log_debug(f"ERROR: {message}")

    def show_success(self, message):
        self.lbl_status.setText("✅ Success!")
        self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
        QMessageBox.information(self, "Success", message)

    def on_process_finished(self):
        self.btn_process.setEnabled(True)
        self.btn_process_batch.setEnabled(len(self.married_folders) > 0)
        if self.auto_exit:
            self.close()

    def start_processing(self):
        if not self.file_queue:
            return
        self.btn_process.setEnabled(False)
        self.progress_bar.setValue(0)
        db_threshold = self.spin_db.value()
        min_duration = self.spin_dur.value()
        
        thread = threading.Thread(
            target=self.run_logic, 
            args=(self.file_queue.copy(), db_threshold, min_duration),
            daemon=True
        )
        thread.start()

    def run_logic(self, queue, db, dur):
        try:
            for file_path in queue:
                self.signals.progress.emit(f"Processing: {os.path.basename(file_path)}")
                
                lower = file_path.lower()
                output_dir = os.path.dirname(file_path)
                
                # Disc Image Workflow (ISO/NRG/CUE)
                if lower.endswith(('.iso', '.nrg', '.cue')):
                    generated_files = self.processor.process_iso_workflow(file_path, output_dir)
                    if generated_files:
                        self.signals.success.emit(f"✅ Extracted {len(generated_files)} tracks from {os.path.basename(file_path)}")
                    else:
                        self.signals.error.emit(f"Failed to process {os.path.basename(file_path)}")
                    continue
                
                # Audio File Workflow (Silence Detection)
                if lower.endswith(('.flac', '.wav', '.mp3', '.m4a')):
                    self.signals.progress.emit("Detecting silence...")
                    tracks = self.processor.detect_silence(file_path, db_threshold=db, min_duration=dur)
                    
                    if not tracks:
                        self.signals.error.emit("No silence detected. Try adjusting threshold.")
                        continue
                    
                    self.signals.progress.emit(f"Found {len(tracks)} tracks. Splitting...")
                    split_files = self.processor.split_file(file_path, tracks, output_dir)
                    
                    if split_files:
                        self.signals.success.emit(f"✅ Split into {len(split_files)} tracks!")
                    continue

            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"Processing Error: {str(e)}")
            self.signals.finished.emit()

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        sys.excepthook = lambda cls, exception, traceback: open("crash_log.txt", "a").write(f"UNCAUGHT: {exception}\n")
        
        window = AutoSplitTagger()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        with open("crash_log.txt", "a") as f:
            f.write(f"CRITICAL STARTUP ERROR: {e}\n")
        print(f"CRITICAL: {e}")
