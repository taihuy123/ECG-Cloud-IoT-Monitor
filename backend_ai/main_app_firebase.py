import sys
import time
import torch
import requests
import numpy as np
import torch.nn as nn
from scipy.signal import find_peaks

# --- CONFIGURATION ---
FIREBASE_URL = "https://ecg-iot-c1b8d-default-rtdb.asia-southeast1.firebasedatabase.app/current_packet.json"
TELEGRAM_TOKEN = "8949102038:AAEY9NmasSg2eUym5ZwRr3xi9EJcy0P1FKk"
TELEGRAM_CHAT_ID = "7967447536"
ALERT_COOLDOWN = 15     

class ECGLSTM(nn.Module):
    def __init__(self, input_size=1, hidden_size=64, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = ECGLSTM().to(device)

# Load Model Weights
try:
    model.load_state_dict(torch.load('ecg_lstm_model.pth', map_location=device))
    model.eval()
    print(f"[INFO] Cloud Worker initialized. Model loaded on {device}")
except Exception as e:
    print(f"[ERROR] Failed to load model weights: {e}")
    sys.exit(1)

# --- TELEGRAM NOTIFIER ---
def send_telegram_alert(packet_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🚨 [ALERT] Anomaly detected via Firebase!\nPacket ID: {packet_id}"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except requests.RequestException:
        print("[ERROR] Failed to send Telegram alert")

# --- MAIN CLOUD POLLING LOOP ---
last_alert_time = 0
last_processed_id = -1  

while True:
    try:
        response = requests.get(FIREBASE_URL, timeout=3)
        if response.status_code != 200:
            print(f"[WARNING] Firebase returned status code: {response.status_code}")
            time.sleep(1.0)
            continue
            
        data = response.json()
        if not data or 'buffer' not in data or 'packet_id' not in data:
            time.sleep(0.5)
            continue
            
        current_packet_id = data['packet_id']
        buffer = data['buffer']
        
        # Process only new and valid packets
        if current_packet_id == last_processed_id or len(buffer) != 720:
            time.sleep(0.2)
            continue
            
        last_processed_id = current_packet_id
        base_time = (current_packet_id - 1) * 2
        print(f"\n[RX] Processing Packet #{current_packet_id} (Base time: {base_time}s)")
        
        signal_mv = (np.array(buffer) - 1024) / 200.0
        signal_centered = signal_mv - np.median(signal_mv)
        
        peaks, _ = find_peaks(np.abs(signal_centered), distance=150, prominence=0.3)
        has_anomaly = False
        
        for pos in peaks:
            if pos - 90 < 0 or pos + 90 >= 720:
                continue
                
            # Precision timestamping: MM:SS.mmm
            t = base_time + (pos / 360.0)
            timestamp = f"{int(t//60):02d}:{int(t%60):02d}.{int((t%1)*1000):03d}"
            
            beat = signal_mv[pos - 90 : pos + 90]
            beat_tensor = torch.tensor(beat, dtype=torch.float32).view(1, -1, 1).to(device)
            
            with torch.no_grad():
                output = model(beat_tensor)
                prob = torch.sigmoid(output).item()
            
            if prob > 0.5:
                print(f"[{timestamp}] WARNING: Anomaly ({prob*100:.1f}%)")
                has_anomaly = True
            else:
                print(f"[{timestamp}] Normal ({prob*100:.1f}%)")
        
        # Trigger Cooldown Alert
        if has_anomaly and (time.time() - last_alert_time > ALERT_COOLDOWN):
            send_telegram_alert(current_packet_id)
            last_alert_time = time.time()
            
        time.sleep(0.2)
        
    except requests.RequestException as net_err:
        print(f"[NET ERROR] Firebase connection failed: {net_err}")
        time.sleep(2.0)
    except Exception as e:
        print(f"[SYSTEM ERROR] {e}")
        time.sleep(1.0)
