#include <WiFi.h>
#include <HTTPClient.h>

// --- CONFIGURATION ---
const char* WIFI_SSID = "Quoc Huy";
const char* WIFI_PASS = "0889063849";
const String FIREBASE_URL = "https://ecg-iot-c1b8d-default-rtdb.asia-southeast1.firebasedatabase.app/current_packet.json";

// --- PIN DEFINITIONS ---
const int PIN_ANALOG_IN = 34;
const int PIN_LO_PLUS = 25;
const int PIN_LO_MINUS = 26;

// --- SAMPLING PARAMETERS ---
const unsigned long SAMPLE_PERIOD_US = 2778; // 360Hz (1,000,000 / 360)
const int MAX_SAMPLES = 720;                 // 2 seconds of data

// Double Buffering Structure
int ecg_buffer_A[MAX_SAMPLES];
int ecg_buffer_B[MAX_SAMPLES];
int* active_buffer = ecg_buffer_A;
int sample_counter = 0;

unsigned long last_sample_time_us = 0;
unsigned long packet_id = 0;

// FreeRTOS Task and Queue
TaskHandle_t UploadTaskHandle = NULL;
QueueHandle_t BufferQueue = NULL;

struct Packet {
    unsigned long id;
    int* data_ptr;
};

// --- CORE 0: NETWORK & UPLOAD TASK ---
void vUploadTask(void *pvParameters) {
    Packet incoming_packet;
    
    while (true) {
        // Wait indefinitely until Core 1 pushes a full buffer into the queue
        if (xQueueReceive(BufferQueue, &incoming_packet, portMAX_DELAY) == pdTRUE) {
            if (WiFi.status() == WL_CONNECTED) {
                // Optimize String allocation to prevent heap fragmentation
                String json_payload;
                json_payload.reserve(MAX_SAMPLES * 6 + 50); 
                
                json_payload = "{\"packet_id\":" + String(incoming_packet.id) + ",\"buffer\":[";
                for (int i = 0; i < MAX_SAMPLES; i++) {
                    json_payload += String(incoming_packet.data_ptr[i]);
                    if (i < MAX_SAMPLES - 1) json_payload += ",";
                }
                json_payload += "]}";

                HTTPClient http;
                http.begin(FIREBASE_URL);
                http.addHeader("Content-Type", "application/json");

                int http_code = http.PUT(json_payload);
                if (http_code > 0) {
                    Serial.printf("[TX] Packet #%lu uploaded successfully. HTTP: %d\n", incoming_packet.id, http_code);
                } else {
                    Serial.printf("[ERROR] HTTP PUT failed: %s\n", http.errorToString(http_code).c_str());
                }
                http.end();
            } else {
                Serial.println("[WIFI] Connection lost. Skipping current packet upload.");
            }
        }
    }
}

// --- STANDARD ARDUINO SETUP ---
void setup() {
    Serial.begin(115200);
    
    pinMode(PIN_LO_PLUS, INPUT);
    pinMode(PIN_LO_MINUS, INPUT);
    
    // Connect to Wi-Fi
    Serial.printf("\n[WIFI] Connecting to SSID: %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n[WIFI] Connected successfully.");

    // Create FreeRTOS Queue for 1 packet pointer
    BufferQueue = xQueueCreate(1, sizeof(Packet));
    if (BufferQueue == NULL) {
        Serial.println("[CRITICAL] Failed to create FreeRTOS Queue.");
        while (1);
    }

    // Pin the Upload Task to Core 0 (Sampling will run on Core 1 by default)
    xTaskCreatePinnedToCore(
        vUploadTask,        // Task function
        "UploadTask",       // Task name
        8192,               // Stack size (8KB)
        NULL,               // Parameters
        1,                  // Priority
        &UploadTaskHandle,  // Task handle
        0                   // Core ID (Core 0)
    );

    last_sample_time_us = micros();
}

// --- CORE 1: TIME-CRITICAL SAMPLING LOOP ---
void loop() {
    unsigned long current_time_us = micros();
    
    if (current_time_us - last_sample_time_us >= SAMPLE_PERIOD_US) {
        last_sample_time_us += SAMPLE_PERIOD_US;
        
        int raw_val = 1024; // Default baseline if leads are off
        
        if (digitalRead(PIN_LO_PLUS) == 0 && digitalRead(PIN_LO_MINUS) == 0) {
            raw_val = analogRead(PIN_ANALOG_IN);
        }
        
        active_buffer[sample_counter++] = raw_val;
        
        // When buffer is full (2 seconds of data)
        if (sample_counter >= MAX_SAMPLES) {
            packet_id++;
            
            // Prepare packet metadata
            Packet packet_to_send = { packet_id, active_buffer };
            
            // Push pointer to Queue for Core 0 to process. Do not block if queue is full.
            if (xQueueSend(BufferQueue, &packet_to_send, 0) != pdTRUE) {
                Serial.printf("[WARNING] Core 0 busy. Packet #%lu dropped to prioritize sampling!\n", packet_id);
            }
            
            // Swap active buffer immediately
            active_buffer = (active_buffer == ecg_buffer_A) ? ecg_buffer_B : ecg_buffer_A;
            sample_counter = 0;
        }
    }
}