# Real-Time ECG Arrhythmia Monitoring System via Cloud IoT and Deep Learning

This repository contains the complete implementation of an end-to-end continuous electrocardiogram (ECG) monitoring and early arrhythmia screening system. The architecture integrates edge hardware biopotential acquisition, low-latency cloud middleware synchronization, and centralized deep learning inference via an LSTM recurrent neural network. The entire project is optimized for extreme cost efficiency, with a hardware production budget constrained under 500,000 VNĐ.

## Core System Features

 Edge Hardware Data Acquisition: High-fidelity biopotential signal conditioning executed at a deterministic 360Hz sampling rate via an AD8232 analog front-end (AFE) and the 12-bit successive-approximation register (SAR) ADC of an ESP32 microcontroller.
 Cloud Middleware Synchronization: Low-latency asynchronous telemetry streaming over Wi-Fi to Firebase Realtime Database using the HTTP REST API PUT method, utilizing sequential overwriting to enforce a zero-growth cloud data footprint.
 Artificial Intelligence Diagnostics: A centralized Python server executing real-time PyTorch inference via a trained Long Short-Term Memory (LSTM) network to classify morphological variations and isolate Premature Ventricular Contractions (PVCs).
 Clinical Visualization Dashboard: A user-friendly HTML5 Canvas web interface designed to render streaming signals dynamically onto a simulated 1mm/5mm thermal grid layout conforming to standard PhysioNet specifications. It includes integrated audio-toggle configurations and an automated interactive incident log.
 Remote Emergency Alerting: Immediate notification dispatch over the Telegram Bot API to cellular devices, delivering accurate diagnostic descriptors alongside millisecond-level precision timestamps.

## Project Directory Structure

 `/hardware_esp32`: Contains the C++ firmware source code for the ESP32 microcontroller, configuring hardware microsecond clocks, lead-off status checking, and Wi-Fi telemetry packaging.
 `/backend_ai`: Contains the centralized Python processing script, the pre-trained PyTorch weight file (`model.pth`), mathematical peak detection modules, and dependent package configuration files.
 `/frontend_web`: Contains the presentation and clinical interaction layer, rendering the web-based medical monitor portal.

## Installation and Deployment Guide

### 1. Edge Hardware Firmware Configuration
 Open `hardware_esp32/esp32_code.ino` using the Arduino IDE.
 Configure your local Wi-Fi credentials (SSID and Password) along with your secure Firebase Realtime Database reference URL.
 Compile and flash the compiled binary onto your ESP32 board.

### 2. Central AI Inference Server Deployment
Navigate to the backend directory, install the required technical libraries, and execute the core application pipeline:
```bash
cd backend_ai
pip install -r requirements.txt
python main_app_firebase.py
