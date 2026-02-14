/*
 * ESP32-CAM WiFi Diagnostic
 * Board: AI Thinker ESP32-CAM | Port: COM4 | Serial: 115200
 * 
 * Step 1: Upload this, open Serial Monitor
 * Step 2: It will SCAN and list networks. Check if yours appears (2.4GHz only!)
 * Step 3: Enter your SSID and password below, upload again
 * Step 4: If phone hotspot: enable it, set to 2.4GHz, use exact name/password
 */

#include <WiFi.h>

const char* ssid     = "YOUR_WIFI_NAME";      // Exact name, case-sensitive
const char* password = "YOUR_WIFI_PASSWORD";  // No extra spaces

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("\n=== ESP32-CAM WiFi Diagnostic ===\n");
  Serial.println("Scanning 2.4GHz networks (takes ~5 sec)...");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  
  int n = WiFi.scanNetworks();
  Serial.print("Found ");
  Serial.print(n);
  Serial.println(" networks:");
  for (int i = 0; i < n; i++) {
    Serial.print("  ");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.print(WiFi.SSID(i));
    Serial.print(" (");
    Serial.print(WiFi.RSSI(i));
    Serial.println(" dBm)");
  }
  Serial.println();
  
  Serial.print("Connecting to: ");
  Serial.println(ssid);
  Serial.println("(If stuck, check: 2.4GHz only, correct password, no typos)\n");
  
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("Stream URL: http://");
    Serial.print(WiFi.localIP());
    Serial.println(":81/stream");
  } else {
    Serial.println("\nCONNECTION FAILED");
    Serial.print("Status code: ");
    Serial.println(WiFi.status());
    Serial.println("Possible causes:");
    Serial.println("- Network is 5GHz (ESP32 needs 2.4GHz)");
    Serial.println("- Wrong password or SSID (check spelling)");
    Serial.println("- Try phone hotspot (2.4GHz)");
  }
}

void loop() {
  delay(5000);
}
