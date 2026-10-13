#include "thingProperties.h"
#include <Arduino_MKRIoTCarrier.h>

MKRIoTCarrier carrier;

// ---- Moisture sensor (Grove connector labelled A0) ----
const int MOISTURE_PIN = A0;
const int RAW_DRY = 850;        // replace with your dry-air reading
const int RAW_WET = 450;        // replace with your in-water reading
const int NO_SIGNAL_BELOW = 20; // raw values this low mean the sensor isn't responding

// ---- Timing ----
const unsigned long INTERVAL_MS = 5000;
unsigned long lastRead = 0;

int lastLight = 0;              // keeps the last good light value between loops

// Average 16 readings to reduce noise
int readAvg(int pin) {
  long sum = 0;
  for (int i = 0; i < 16; i++) {
    sum += analogRead(pin);
    delay(2);
  }
  return sum / 16;
}

int readLight() {
  int r, g, b, clear = lastLight;
  unsigned long start = millis();
  while (!carrier.Light.colorAvailable() && millis() - start < 200) {
    delay(5);
  }
  if (carrier.Light.colorAvailable()) {
    carrier.Light.readColor(r, g, b, clear);
    lastLight = clear;
  }
  return lastLight;
}

void setup() {
  Serial.begin(9600);
  delay(1500);

  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);
  setDebugMessageLevel(2);
  ArduinoCloud.printDebugInfo();

  CARRIER_CASE = false;         // set true if the carrier is in its case
  carrier.begin();
  carrier.display.setRotation(0);
  carrier.display.fillScreen(ST77XX_BLACK);

  Serial.println("ms,temperature_C,humidity_pct,pressure_kPa,light,moisture_raw,moisture_pct");
}

void loop() {
  ArduinoCloud.update();        // must run often to keep the Cloud connection alive

  if (millis() - lastRead >= INTERVAL_MS) {
    lastRead = millis();

    // ---- Read sensors ----
    temperature = carrier.Env.readTemperature();
    humidity    = carrier.Env.readHumidity();
    pressure    = carrier.Pressure.readPressure();
    light       = readLight();

    int raw = readAvg(MOISTURE_PIN);
    bool noSignal = (raw < NO_SIGNAL_BELOW);
    moisture = noSignal ? 0 : constrain(map(raw, RAW_DRY, RAW_WET, 0, 100), 0, 100);

    // ---- Carrier display ----
    carrier.display.fillScreen(ST77XX_BLACK);
    carrier.display.setTextColor(ST77XX_WHITE);
    carrier.display.setTextSize(2);

    carrier.display.setCursor(30, 50);
    carrier.display.print("Hum: ");   carrier.display.print(humidity, 1); carrier.display.print(" %");
    carrier.display.setCursor(30, 80);
    carrier.display.print("Prs: ");   carrier.display.print(pressure, 1); carrier.display.print(" kPa");
    carrier.display.setCursor(30, 110);
    carrier.display.print("Light: "); carrier.display.print(light);
    carrier.display.setCursor(30, 140);
    carrier.display.print("Soil: ");
    if (noSignal) {
      carrier.display.print("no signal");
    } else {
      carrier.display.print(moisture); carrier.display.print(" %");
    }

    // ---- Serial log (CSV, you can copy it into Excel for the report) ----
    Serial.print(millis());       Serial.print(",");
    Serial.print(temperature, 1); Serial.print(",");
    Serial.print(humidity, 1);    Serial.print(",");
    Serial.print(pressure, 2);    Serial.print(",");
    Serial.print(light);          Serial.print(",");
    Serial.print(raw);            Serial.print(",");
    Serial.println(moisture);
  }
}