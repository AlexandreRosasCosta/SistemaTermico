#include <math.h>
#include <WiFi.h>
#include <PubSubClient.h>

// ==== PINAGEM ESP32 ====
const uint8_t PIN_ZC   = 27;   // zero-cross (H11AA1)
const uint8_t PIN_MOC  = 26;   // MOC3023
const uint8_t PIN_TEMP = 34;   // NTC
#define PIN_NTC PIN_TEMP;

// ==== Controle de fase ====
volatile unsigned long semiStartUs = 0;
volatile bool newSemi = false;

// Contagem / debug zero-cross
volatile unsigned long lastZeroUs = 0;
volatile unsigned long zeroCount  = 0;

// Atraso de disparo
const unsigned long MIN_DELAY_US = 100;
const unsigned long MAX_DELAY_US = 9900;

unsigned long delay_us = MAX_DELAY_US;
float powerPercent = 0.0;

// --- Termistor ---
const double R_NOMINAL = 10000.0;
const double R_SERIE   = 13850.0;
const double BETA      = 3950.0;
const double T_NOMINAL = 298.15;
const int    AMOSTRAS  = 20;

// ===== Converte powerPercent em delay_us =====
void updateDelayFromPower()
{
  if (powerPercent < 0.0f)   powerPercent = 0.0f;
  if (powerPercent > 100.0f) powerPercent = 100.0f;

  if (powerPercent == 0.0f) {
    delay_us = 0; // não dispara o trigger
    return;
  }

  float power = powerPercent / 100.0f;
  delay_us = MAX_DELAY_US - (unsigned long)(power * (MAX_DELAY_US - MIN_DELAY_US));
}

// ===== ISR ZERO CROSS =====
void IRAM_ATTR onZeroCross() {
  unsigned long now = micros();
  // filtro de ruído / bounces
  if (now - lastZeroUs > 8500) {
    semiStartUs = now;
    newSemi     = true;
    zeroCount++;
  }
  lastZeroUs = now;
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_ZC,  INPUT_PULLUP);
  pinMode(PIN_MOC, OUTPUT);
  digitalWrite(PIN_MOC, LOW);

  pinMode(PIN_TEMP, INPUT);
  analogReadResolution(12);     // ADC 0..4095

  attachInterrupt(digitalPinToInterrupt(PIN_ZC), onZeroCross, FALLING);

  Serial.println("=== Dimmer ESP32 + Termistor ===");
  Serial.println("Digite um valor de potência entre 0 e 100 (%) e pressione Enter.");
  updateDelayFromPower();
}

// ======================= LOOP =========================
void loop() {
  // 1) CONTROLE DE FASE / TRIGGER  --------------------
  if (newSemi) {
    newSemi = false;
    if (powerPercent > 0.0f && delay_us > 0) {
      unsigned long fireTime = semiStartUs + delay_us;
      // espera até chegar na posição
      while ((long)(micros() - fireTime) < 0) { }
      digitalWrite(PIN_MOC, HIGH);
      delayMicroseconds(100);
      digitalWrite(PIN_MOC, LOW);
    }
  }

  // 2) LEITURA DO SERIAL PRA DEFINIR POTÊNCIA --------
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
      float val = input.toFloat();
      if (val >= 0.0f && val <= 100.0f) {
        powerPercent = val;
        updateDelayFromPower();
        Serial.print("Potência ajustada para: ");
        Serial.print(powerPercent, 3);
        Serial.print("% | Delay_us: ");
        Serial.println(delay_us);
      } else {
        Serial.println("Digite um valor entre 0 e 100.");
      }
    }
  }

  // 3) LEITURA DO TERMISTOR -----------
  static unsigned long lastTempMs = 0;
  if (millis() - lastTempMs > 500) {
    lastTempMs = millis();

    long soma_adc = 0;
    for (int i = 0; i < AMOSTRAS; i++) {
      soma_adc += analogRead(PIN_TEMP);
    }
    double adc_medio = soma_adc / (double)AMOSTRAS;

    Serial.print("ADC: ");
    Serial.print(adc_medio);

    if (adc_medio < 100 || adc_medio > 4000) {
      Serial.println(" -> ERRO ADC");
    } else {
      double resistencia_ntc =
        R_SERIE * (adc_medio / (4095.0 - adc_medio));
      double temperatura_kelvin =
        1.0 / ( (1.0 / T_NOMINAL) + (log(resistencia_ntc / R_NOMINAL) / BETA) );
      double temperatura_celsius = temperatura_kelvin - 273.15;

      Serial.print(" | Temp: ");
      Serial.print(temperatura_celsius);
      Serial.println(" °C");
    }
  }

  // 4) DEBUG DO DIMMER --------------------------------
  static unsigned long lastSendMs = 0;
  if (millis() - lastSendMs > 1000) {
    lastSendMs = millis();
    Serial.print("ZC: ");
    Serial.print(zeroCount);
    Serial.print(" | Potência: ");
    Serial.print(powerPercent, 3);
    Serial.print("% | Delay_us: ");
    Serial.println(delay_us);
  }
}
