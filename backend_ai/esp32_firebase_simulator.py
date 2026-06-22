import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import requests
import wfdb

# Configuration
FIREBASE_URL = "16542156"
CHUNK_SIZE = 720  # 2 seconds of data at 360Hz
FS = 360
INTERVAL = CHUNK_SIZE / FS  # Exactly 2.0 seconds

# --- FILE SELECTION ---
root = tk.Tk()
root.withdraw()

print("[INFO] Opening file dialog...")
file_path_str = filedialog.askopenfilename(
    title="Select ECG Data File (.csv or .hea)",
    filetypes=[
        ("ECG All Formats", "*.csv *.hea"),
        ("CSV Files", "*.csv"),
        ("WFDB Header Files", "*.hea")
    ]
)

if not file_path_str:
    print("[ERROR] No file selected. Exiting.")
    sys.exit(1)

file_path = Path(file_path_str)
print(f"[INFO] Selected file: {file_path.name}")

ecg_signal = []

# --- DATA PARSING ---
try:
    if file_path.suffix.lower() == '.csv':
        df = pd.read_csv(file_path)
        df.columns = [c.strip() for c in df.columns]
        
        # Priority for MLII lead, fallback to first column
        if 'MLII' in df.columns:
            ecg_signal = df['MLII'].dropna().tolist()
        else:
            ecg_signal = df.iloc[:, 0].dropna().tolist()
        print("[INFO] Mode: Parsed CSV format.")

    elif file_path.suffix.lower() == '.hea':
        # wfdb requires path without extension
        record_path = str(file_path.with_suffix(''))
        record = wfdb.rdrecord(record_path)
        
        if 'MLII' in record.sig_name:
            channel_idx = record.sig_name.index('MLII')
            signal_mv = record.p_signal[:, channel_idx]
        else:
            signal_mv = record.p_signal[:, 0]
            print(f"[WARNING] MLII channel not found. Using first channel: '{record.sig_name[0]}'")
            
        # Reverse calibration: Convert mV back to raw 12-bit ADC values
        ecg_signal = (signal_mv * 200.0 + 1024).tolist()
        print("[INFO] Mode: Parsed WFDB format.")

    print(f"[INFO] Successfully loaded {len(ecg_signal)} samples.")

except Exception as e:
    print(f"[ERROR] Failed to parse data file: {e}")
    sys.exit(1)

# --- STREAMING LOOP ---
packet_id = 0
pointer = 0

while pointer + CHUNK_SIZE <= len(ecg_signal):
    start_time = time.perf_counter()
    packet_id += 1
    
    # Extract 2-second window
    packet_buffer = ecg_signal[pointer : pointer + CHUNK_SIZE]
    pointer += CHUNK_SIZE
    
    payload = {
        "packet_id": packet_id,
        "buffer": packet_buffer
    }
    
    print(f"[TX] Syncing packet {packet_id} (Samples {pointer-CHUNK_SIZE} -> {pointer}) to Firebase...")
    
    try:
        # Use PUT method to overwrite node and prevent database bloat
        response = requests.put(FIREBASE_URL, json=payload, timeout=3)
        if response.status_code == 200:
            print("     -> [OK] Cloud synced successfully.")
        else:
            print(f"     -> [FAIL] Firebase rejected with status: {response.status_code}")
    except requests.RequestException as e:
        print(f"     -> [FAIL] Network error: {e}")
        
    # High-precision real-time emulation (compensates for network request latency)
    elapsed = time.perf_counter() - start_time
    if elapsed < INTERVAL:
        time.sleep(INTERVAL - elapsed)

print("[INFO] Transmission completed. All packets sent.")
