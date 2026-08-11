#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <mbedtls/md.h>

// Network Settings
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* mqtt_server = "192.168.1.100"; // Replace with Backend IP

WiFiClient espClient;
PubSubClient client(espClient);

// Vehicle Data
const char* vehicle_id = "V3";
float lat = 17.4250;
float lon = 78.4483;
float speed_kmph = 35.0;
float heading_deg = 180.0;
const char* vehicle_type = "Passenger";

// HMAC Secret
const char* secret_key = "v2v_shared_secret_123";

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect(vehicle_id)) {
      Serial.println("connected");
      // Bi-directional transfer: subscribe to receive threats and commands
      client.subscribe("v2v/alerts/#");
      client.subscribe("v2v/commands");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

String generateSignature(String payloadToSign) {
  byte hmacResult[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_type_t md_type = MBEDTLS_MD_SHA256;
  
  const size_t payloadLength = payloadToSign.length();
  const size_t keyLength = strlen(secret_key);
  
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(md_type), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char *) secret_key, keyLength);
  mbedtls_md_hmac_update(&ctx, (const unsigned char *) payloadToSign.c_str(), payloadLength);
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);
  
  String hexStr = "";
  for(int i= 0; i< 32; i++){
    char str[3];
    sprintf(str, "%02x", (int)hmacResult[i]);
    hexStr += str;
  }
  return hexStr;
}

// MQTT Callback for receiving data from Backend
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String messageTemp;
  for (int i = 0; i < length; i++) {
    messageTemp += (char)payload[i];
  }
  
  String t = String(topic);
  if (t.startsWith("v2v/alerts/")) {
    Serial.println("\n[!!!] CRITICAL: COLLISION ALERT RECEIVED FROM V2V NETWORK!");
    Serial.println("      ENGAGING AUTOMATIC EMERGENCY BRAKING (AEB)");
    Serial.println("      PAYLOAD: " + messageTemp + "\n");
    // digitalWrite(AEB_RELAY_PIN, HIGH); // Example hardware trigger
  } else if (t == "v2v/commands") {
    Serial.println("\n[*] BROADCAST COMMAND RECEIVED:");
    Serial.println("    " + messageTemp + "\n");
  }
}

void setup() {
  Serial.begin(115200);
  setup_wifi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(mqttCallback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Simulate movement (moving south)
  lat -= 0.0001; 
  unsigned long timestamp = millis() / 1000 + 1730000000; // Simulated Unix time

  // Create JSON document
  StaticJsonDocument<256> doc;
  doc["vehicle_id"] = vehicle_id;
  doc["vehicle_type"] = vehicle_type;
  doc["timestamp"] = timestamp;
  doc["lat"] = lat;
  doc["lon"] = lon;
  doc["speed_kmph"] = speed_kmph;
  doc["heading_deg"] = heading_deg;

  // Sign data (MUST match backend format exactly)
  String sign_str = String(vehicle_id) + String(vehicle_type) + String(timestamp) + String(lat, 6) + String(lon, 6) + String(speed_kmph, 1) + String(heading_deg, 0);
  doc["signature"] = generateSignature(sign_str);

  char buffer[256];
  serializeJson(doc, buffer);

  Serial.print("Publishing: ");
  Serial.println(buffer);
  
  client.publish("v2v/telemetry", buffer);
  
  delay(100); // 10Hz telemetry
}
