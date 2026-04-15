/*******************************************************
 * Smart Crop Recommendation System with Button Control
 * Components: OLED (SSD1306), DHT22, LDR, Soil Moisture Sensor, Button
 * Data Source: PiliSeed Backend API
 * Button toggles between sensor data and crop recommendations
 * Displays top 3 crop recommendations from AI
 *******************************************************/

// >>>>> 1. LIBRARY INCLUSIONS <<<<<
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

// >>>>> 2. CONFIGURATION (CREDENTIALS) <<<<<
// Create config.h from config.h.example with your credentials.
// config.h is gitignored - never commit sensitive data.
#include "config.h"

// >>>>> 3. PIN DEFINITIONS & CONSTANTS <<<<<
#define DHTPIN 4
#define DHTTYPE DHT22
#define LDR_PIN 32
#define SOIL_MOISTURE_PIN 33
#define BUTTON_PIN 5
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

// >>>>> 4. WIFI AND API CREDENTIALS (from config.h) <<<<<
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* backendUrl = BACKEND_URL;
const char* sensorId = SENSOR_ID;

// >>>>> 5. SENSOR AND DISPLAY OBJECTS <<<<<
DHT dht(DHTPIN, DHTTYPE);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// >>>>> 6. STATE VARIABLES <<<<<
bool showingPlants = false;    // Track what we're currently displaying
bool buttonPressed = false;    // Track button state to avoid multiple triggers
String recommendedCrops[3];    // Store the top 3 recommended crops
String recommendationMessage;  // Short backend message
int cropCount = 0;             // Number of crops received

// >>>>> 7. SENSOR READING FUNCTIONS <<<<<
float readTemperature() {
  float t = dht.readTemperature();
  if (isnan(t)) {
    Serial.println("[ERROR] Failed to read temperature");
    return -999;
  }
  Serial.print("[OK] Temperature: ");
  Serial.print(t);
  Serial.println(" C");
  return t;
}

float readHumidity() {
  float h = dht.readHumidity();
  if (isnan(h)) {
    Serial.println("[ERROR] Failed to read humidity");
    return -999;
  }
  Serial.print("[OK] Humidity: ");
  Serial.print(h);
  Serial.println("%");
  return h;
}

float readLightLevel() {
  int rawValue = analogRead(LDR_PIN);
  // Convert raw analog reading to lux (approximate mapping)
  // Assuming 0-4095 maps to 0-20000 lux
  float lux = map(rawValue, 0, 4095, 0, 20000);
  Serial.print("[OK] Light Level (raw): ");
  Serial.print(rawValue);
  Serial.print(" -> ");
  Serial.print(lux);
  Serial.println(" lux");
  return lux;
}

float readSoilMoisture() {
  int rawValue = analogRead(SOIL_MOISTURE_PIN);
  // Convert raw analog reading to percentage
  // Assuming 0 (wet) to 4095 (dry), invert to get moisture percentage
  float moisturePct = map(rawValue, 4095, 0, 0, 100);
  moisturePct = constrain(moisturePct, 0, 100);
  Serial.print("[OK] Soil Moisture (raw): ");
  Serial.print(rawValue);
  Serial.print(" -> ");
  Serial.print(moisturePct);
  Serial.println("%");
  return moisturePct;
}

// >>>>> 8. OLED DISPLAY FUNCTIONS <<<<<
void displayMessage(const String& message, int textSize = 1) {
  display.clearDisplay();
  display.setTextSize(textSize);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(message);
  display.display();
}

void displaySensorData(float temp, float humidity, float light, float moisture) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);

  display.print("Temp: ");
  display.print(temp, 1);
  display.println("C");

  display.print("Humidity: ");
  display.print(humidity, 1);
  display.println("%");

  display.print("Light: ");
  display.print(light, 0);
  display.println(" lux");

  display.print("Soil: ");
  display.print(moisture, 1);
  display.println("%");

  display.println("");
  display.println("Press button for");
  display.println("crop suggestions");
  display.display();
}

void displayCropRecommendations() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Top 3 Pananim:");
  display.println("");

  if (cropCount > 0) {
    for (int i = 0; i < cropCount && i < 3; i++) {
      String cropName = recommendedCrops[i];

      // Trim long names to fit screen (21 chars max)
      if (cropName.length() > 21) {
        cropName = cropName.substring(0, 18) + "...";
      }

      display.print((i + 1));
      display.print(". ");
      display.println(cropName);
    }

    display.println("");
    display.println("Press btn for data");
  } else {
    display.println("No crops found");
    display.println("");
    display.println("Check connection");
    display.println("or sensor data");
  }

  display.display();
}

void displayError(const String& error) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Error:");
  display.println("");
  display.println(error);
  display.println("");
  display.println("Press btn to retry");
  display.display();
}

void displayProcessing() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Processing...");
  display.println("");
  display.println("Analyzing sensor");
  display.println("data with AI...");
  display.println("");
  display.println("This may take up");
  display.println("to 2 minutes...");
  display.display();
}

// >>>>> 9. API REQUEST FUNCTION <<<<<
void getCropRecommendations(float temp, float humidity, float light, float moisture) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[ERROR] WiFi not connected");
    displayError("WiFi Disconnected");
    return;
  }

  Serial.println("\n=======================================");
  Serial.println("Sending sensor data to PiliSeed API");
  Serial.println("=======================================");

  HTTPClient http;

  // Construct the API endpoint URL
  String url = String(backendUrl) + "/recommendations/hardware/" + String(sensorId) + "/readings";
  Serial.print("Endpoint: ");
  Serial.println(url);

  // Create JSON payload
  StaticJsonDocument<256> jsonDoc;
  jsonDoc["soil_moisture_pct"] = moisture;
  jsonDoc["temperature_c"] = temp;
  jsonDoc["humidity_pct"] = humidity;
  jsonDoc["light_lux"] = light;

  String jsonPayload;
  serializeJson(jsonDoc, jsonPayload);

  Serial.println("\nSending data:");
  Serial.println(jsonPayload);

  // Configure HTTP request
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(120000);  // 120 second timeout

  displayProcessing();

  // Send POST request
  Serial.println("\nWaiting for AI response...");
  int httpCode = http.POST(jsonPayload);

  Serial.print("HTTP Status Code: ");
  Serial.println(httpCode);

  if (httpCode == HTTP_CODE_OK || httpCode == 200) {
    String response = http.getString();
    Serial.println("\nResponse received:");
    Serial.println(response);

    // Parse JSON response
    DynamicJsonDocument responseDoc(2048);
    DeserializationError error = deserializeJson(responseDoc, response);

    if (!error) {
      if (!responseDoc.containsKey("top_3_crops")) {
        Serial.println("[ERROR] Missing top_3_crops in response");
        displayError("Invalid API format");
        http.end();
        return;
      }

      for (int i = 0; i < 3; i++) {
        recommendedCrops[i] = "";
      }

      JsonArray cropsArray = responseDoc["top_3_crops"].as<JsonArray>();
      cropCount = cropsArray.size();
      if (cropCount > 3) cropCount = 3;

      recommendationMessage = responseDoc["message"] | "";
      int totalCrops = responseDoc["total_crops_generated"] | cropCount;

      Serial.println("\n[OK] Recommended crops:");
      for (int i = 0; i < cropCount; i++) {
        recommendedCrops[i] = cropsArray[i].as<String>();
        Serial.print("  ");
        Serial.print(i + 1);
        Serial.print(". ");
        Serial.println(recommendedCrops[i]);
      }

      // Safety fill if backend response is unexpectedly short.
      while (cropCount < 3) {
        recommendedCrops[cropCount] = "N/A";
        cropCount++;
      }

      Serial.print("\nMessage: ");
      Serial.println(recommendationMessage);
      Serial.print("Total crops generated: ");
      Serial.println(totalCrops);
      Serial.println("=======================================\n");

      showingPlants = true;
      displayCropRecommendations();
    } else {
      Serial.print("[ERROR] JSON parsing failed: ");
      Serial.println(error.c_str());
      displayError("JSON Parse Error");
    }
  } else if (httpCode > 0) {
    Serial.print("[ERROR] HTTP Error: ");
    Serial.println(httpCode);

    String errorResponse = http.getString();
    Serial.println("Error response:");
    Serial.println(errorResponse);

    displayError("HTTP Error " + String(httpCode));
  } else {
    Serial.print("[ERROR] Connection failed: ");
    Serial.println(http.errorToString(httpCode));
    displayError("Connection Failed");
  }

  http.end();
}

// >>>>> 10. SETUP AND LOOP <<<<<
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n");
  Serial.println("=======================================");
  Serial.println("PiliSeed Smart Crop System");
  Serial.println("=======================================");

  // Initialize OLED display
  Serial.println("Initializing OLED display...");
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[ERROR] SSD1306 allocation failed");
    for(;;);
  }
  Serial.println("[OK] OLED initialized");

  display.clearDisplay();
  displayMessage("PiliSeed System\nStarting...", 1);

  // Initialize DHT sensor
  Serial.println("Initializing DHT22 sensor...");
  dht.begin();
  Serial.println("[OK] DHT22 initialized");

  // Initialize analog pins and button
  Serial.println("Initializing pins...");
  pinMode(LDR_PIN, INPUT);
  pinMode(SOIL_MOISTURE_PIN, INPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.println("[OK] Pins configured");

  // Connect to WiFi
  Serial.println("\nConnecting to WiFi...");
  Serial.print("SSID: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  displayMessage("Connecting to\nWiFi...", 1);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[OK] WiFi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    displayMessage("WiFi Connected!\n" + WiFi.localIP().toString(), 1);
  } else {
    Serial.println("[ERROR] WiFi connection failed");
    displayMessage("WiFi Failed!\nCheck credentials", 1);
  }

  Serial.println("=======================================");
  Serial.println("System ready");
  Serial.println("=======================================\n");

  delay(2000);
}

void loop() {
  // Read all sensors
  float temperature = readTemperature();
  float humidity = readHumidity();
  float lightLevel = readLightLevel();
  float soilMoisture = readSoilMoisture();

  // Check if button is pressed (LOW because of INPUT_PULLUP)
  if (digitalRead(BUTTON_PIN) == LOW && !buttonPressed) {
    buttonPressed = true;

    Serial.println("\nButton pressed");

    if (!showingPlants) {
      // Currently showing sensors, now get crop recommendations
      Serial.println("Switching to crop recommendations mode");

      // Validate sensor readings
      if (temperature == -999 || humidity == -999) {
        Serial.println("[ERROR] Invalid sensor readings detected");
        displayError("Sensor Error!");
        delay(2000);
        displaySensorData(temperature, humidity, lightLevel, soilMoisture);
      } else {
        // Get recommendations from API
        getCropRecommendations(temperature, humidity, lightLevel, soilMoisture);
      }
    } else {
      // Currently showing crops, return to sensor display
      Serial.println("Returning to sensor data display");
      showingPlants = false;
      displaySensorData(temperature, humidity, lightLevel, soilMoisture);
    }

    delay(500);  // Debounce delay
  }

  // Reset button state when released
  if (digitalRead(BUTTON_PIN) == HIGH) {
    buttonPressed = false;
  }

  // Update display based on current mode
  if (!showingPlants) {
    displaySensorData(temperature, humidity, lightLevel, soilMoisture);
  }

  delay(100);  // Small delay for efficient looping
}
