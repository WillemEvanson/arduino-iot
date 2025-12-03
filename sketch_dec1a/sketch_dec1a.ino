#include <ESP8266WiFi.h>

#include <Arduino.h>
#include <bearssl/bearssl.h>
#include <cbor.h>
#include <PubSubClient.h>
#include <WiFiClientSecureBearSSL.h>
#include <WiFiUdp.h>
#include <NTPClient.h>

#include <string.h>

const uint8_t HMAC_KEY[32] = {
    0x71, 0x33, 0x54, 0x02, 0x77, 0xE6, 0x27, 0x8E,
    0x0F, 0x52, 0xC3, 0x91, 0x5A, 0x8A, 0xAF, 0x74,
    0xAB, 0x56, 0xCE, 0xF7, 0xED, 0x2E, 0x50, 0x91,
    0xEC, 0x36, 0x6B, 0xE2, 0xB2, 0xF0, 0x71, 0xDC};

const char *WIFI_SSID = "laptop";
const char *WIFI_PASSWORD = "password";

const char *MQTT_CLIENT_NAME = "ESP8266Client";
// const char *MQTT_SERVER_NAME = "10.42.0.1";  // original
const char *MQTT_SERVER_NAME = "10.42.0.1";
const int MQTT_PORT = 1883;

WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 0, 60000);

WiFiClient WIFI_CLIENT;
PubSubClient MQTT_CLIENT(WIFI_CLIENT);

size_t encodeTemperature(uint8_t *buf, size_t buf_size,
                         const char *device_id,
                         uint64_t ts,
                         double temperature)
{
  CborEncoder encoder, array;
  cbor_encoder_init(&encoder, buf, buf_size, 0);

  CborError err = cbor_encoder_create_array(&encoder, &array, 5);
  if (err != CborNoError)
    return 0;

  cbor_encode_uint(&array, (uint64_t)1);
  cbor_encode_text_stringz(&array, device_id);
  cbor_encode_uint(&array, ts);
  cbor_encode_double(&array, temperature);
  uint8_t sig[32] = {0};
  cbor_encode_byte_string(&array, sig, sizeof(sig));

  err = cbor_encoder_close_container(&encoder, &array);
  if (err != CborNoError)
    return 0;

  return cbor_encoder_get_buffer_size(&encoder, buf);
}

size_t encodeMotion(uint8_t *buf, size_t buf_size,
                    const char *device_id,
                    uint64_t ts,
                    bool motion)
{
  CborEncoder encoder, array;
  cbor_encoder_init(&encoder, buf, buf_size, 0);

  CborError err = cbor_encoder_create_array(&encoder, &array, 5);
  if (err != CborNoError)
    return 0;

  cbor_encode_uint(&array, (uint64_t)2);
  cbor_encode_text_stringz(&array, device_id);
  cbor_encode_uint(&array, ts);
  cbor_encode_boolean(&array, motion);
  uint8_t sig[32] = {0};
  cbor_encode_byte_string(&array, sig, sizeof(sig));

  err = cbor_encoder_close_container(&encoder, &array);
  if (err != CborNoError)
    return 0;

  return cbor_encoder_get_buffer_size(&encoder, buf);
}

size_t encodeDoor(uint8_t *buf, size_t buf_size,
                  const char *device_id,
                  uint64_t ts,
                  bool door_open)
{
  CborEncoder encoder, array;
  cbor_encoder_init(&encoder, buf, buf_size, 0);

  CborError err = cbor_encoder_create_array(&encoder, &array, 5);
  if (err != CborNoError)
    return 0;

  cbor_encode_uint(&array, (uint64_t)3);
  cbor_encode_text_stringz(&array, device_id);
  cbor_encode_uint(&array, ts);
  cbor_encode_boolean(&array, door_open);
  uint8_t sig[32] = {0};
  cbor_encode_byte_string(&array, sig, sizeof(sig));

  err = cbor_encoder_close_container(&encoder, &array);
  if (err != CborNoError)
    return 0;

  return cbor_encoder_get_buffer_size(&encoder, buf);
}

size_t encodeCurtain(uint8_t *buf, size_t buf_size,
                     const char *device_id,
                     uint64_t ts,
                     uint64_t curtain)
{
  CborEncoder encoder, array;
  cbor_encoder_init(&encoder, buf, buf_size, 0);

  CborError err = cbor_encoder_create_array(&encoder, &array, 5);
  if (err != CborNoError)
    return 0;

  cbor_encode_uint(&array, (uint64_t)4);
  cbor_encode_text_stringz(&array, device_id);
  cbor_encode_uint(&array, ts);
  cbor_encode_uint(&array, curtain);
  uint8_t sig[32] = {0};
  cbor_encode_byte_string(&array, sig, sizeof(sig));

  err = cbor_encoder_close_container(&encoder, &array);
  if (err != CborNoError)
    return 0;

  return cbor_encoder_get_buffer_size(&encoder, buf);
}

void compute_hmac(const uint8_t *data, size_t data_len, uint8_t *out)
{
  br_hmac_key_context hmac_key;
  br_hmac_context hmac_ctx;

  br_hmac_key_init(&hmac_key, &br_sha256_vtable, HMAC_KEY, sizeof(HMAC_KEY));
  br_hmac_init(&hmac_ctx, &hmac_key, 32);
  br_hmac_update(&hmac_ctx, data, data_len);
  br_hmac_out(&hmac_ctx, out);
}

void apply_hmac_inplace(uint8_t *buf, size_t len)
{
  if (len < 32)
    return;

  size_t sig_offset = len - 32;

  uint8_t hmac_out[32];
  compute_hmac(buf, sig_offset, hmac_out);

  memcpy(buf + sig_offset, hmac_out, 32);
}

unsigned long update_interval = 1000;
unsigned long prev_update_millis = 0;

unsigned long curtain_update_interval = 500;
unsigned long prev_curtain_millis = 0;
uint64_t curtain_rate_per_second = 10;
int64_t curtain_position = 0;
int64_t curtain_target = 0;


void callback(char *topic, uint8_t *payload, size_t payload_len)
{
  // The only command we support here is changing the curtain position.
  CborParser parser;
  CborValue root, elem;
  cbor_parser_init(payload, payload_len, 0, &parser, &root);
  if (!cbor_value_is_array(&root))
    return;

  CborValue it;
  cbor_value_enter_container(&root, &it);

  int64_t type;
  cbor_value_get_int64(&it, &type);
  cbor_value_advance(&it);

  char device_id[32];
  size_t device_id_len = sizeof(device_id);
  cbor_value_copy_text_string(&it, device_id, &device_id_len, NULL);
  cbor_value_advance(&it);

  int64_t timestamp;
  cbor_value_get_int64(&it, &timestamp);
  cbor_value_advance(&it);

  int64_t value;
  cbor_value_get_int64(&it, &value);
  cbor_value_advance(&it);

  uint8_t hmac_buf[32];
  size_t hmac_len = sizeof(hmac_buf);
  cbor_value_copy_byte_string(&it, hmac_buf, &hmac_len, &it);

  uint8_t validation_buf[32];
  compute_hmac(payload, payload_len - 32, validation_buf);
  if (memcmp(hmac_buf, validation_buf, 32) != 0)
  {
    Serial.println("Invalid HMAC");
    return;
  }

  if (type != 1) {
    Serial.println("Received unexpected packet");
    return;
  }

  Serial.println("Received Packet:");
  Serial.print(" Type: ");
  Serial.println(type);
  Serial.print(" Device ID: ");
  Serial.println(device_id);
  Serial.print(" Timestamp: ");
  Serial.println(timestamp);
  Serial.print(" Target Position: ");
  Serial.println(value);

  value = max((uint64_t)0, min((uint64_t)value, (uint64_t)100));

  prev_curtain_millis = millis();
  curtain_target = value;
}

void setup()
{
  // Wait for serial monitor to start
  delay(3000);

  // Set up serial port for tracing information
  Serial.begin(9600);

  // Connect to Wi-Fi
  Serial.println("Connecting to Wi-Fi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20)
  {
    delay(500);
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("\nWi-Fi Connected!");
    Serial.print("IP Address: ");
    IPAddress ip = WiFi.localIP();
    Serial.print(ip[0]);
    Serial.print(".");
    Serial.print(ip[1]);
    Serial.print(".");
    Serial.print(ip[2]);
    Serial.print(".");
    Serial.println(ip[3]);
  }
  else
  {
    Serial.println("\nFailed to connect to Wi-Fi. Please check your credentials.");
    while (true) {
      asm("");
    }
  }

  // Get time
  timeClient.begin();

  // Connect to MQTT
  Serial.print("Connecting to MQTT Server...");
  MQTT_CLIENT.setServer(MQTT_SERVER_NAME, MQTT_PORT);
  while (!MQTT_CLIENT.connected())
  {
    if (MQTT_CLIENT.connect(MQTT_CLIENT_NAME))
    {
      Serial.println("\nMQTT connected");
      MQTT_CLIENT.setCallback(callback);
      MQTT_CLIENT.subscribe("blinds/commands");
    }
    else
    {
      Serial.print(".");
      delay(1000);
    }
  }
}

void loop()
{
  unsigned long current_millis = millis();
  if (current_millis - prev_update_millis >= update_interval) {
    prev_update_millis = current_millis;


    Serial.println("Sending new packet");
    uint64_t ts = timeClient.getEpochTime();

    uint64_t startTime = micros();
    uint selection = random(0, 100);
    if (selection < 5)
    {
      bool door_open = random(0, 2);

      uint8_t cbor_buffer[192];
      size_t cbor_len = encodeDoor(cbor_buffer, sizeof(cbor_buffer), MQTT_CLIENT_NAME, ts, door_open);
      apply_hmac_inplace(cbor_buffer, cbor_len);
      MQTT_CLIENT.publish("blinds/door", cbor_buffer, cbor_len);
    }
    else if (selection < 25)
    {
      double temperature = random(50, 80);

      uint8_t cbor_buffer[192];
      size_t cbor_len = encodeTemperature(cbor_buffer, sizeof(cbor_buffer), MQTT_CLIENT_NAME, ts, temperature);
      apply_hmac_inplace(cbor_buffer, cbor_len);
      MQTT_CLIENT.publish("blinds/temperature", cbor_buffer, cbor_len);
    }
    else
    {
      bool motion = random(0, 2);

      uint8_t cbor_buffer[192];
      size_t cbor_len = encodeMotion(cbor_buffer, sizeof(cbor_buffer), MQTT_CLIENT_NAME, ts, motion);
      apply_hmac_inplace(cbor_buffer, cbor_len);
      MQTT_CLIENT.publish("blinds/motion", cbor_buffer, cbor_len);
    }
  }

  current_millis = millis();
  long delta_time = current_millis - prev_curtain_millis;
  if (delta_time >= curtain_update_interval && curtain_position != curtain_target) {
    prev_curtain_millis = current_millis;

    int64_t delta = curtain_target - curtain_position;
    int64_t clamped_delta = delta_time * curtain_rate_per_second / 1000;
    Serial.print("Clamped Delta: ");
    Serial.print(clamped_delta);
    Serial.println();

    if (abs(delta) <= clamped_delta)
    {
      curtain_position = curtain_target;
    }
    else if (delta < 0)
    {
      curtain_position -= clamped_delta;
    }
    else
    {
      curtain_position += clamped_delta;
    }

    uint64_t ts = timeClient.getEpochTime();

    uint8_t cbor_buffer[192];
    size_t cbor_len = encodeCurtain(cbor_buffer, sizeof(cbor_buffer), MQTT_CLIENT_NAME, ts, curtain_position);
    apply_hmac_inplace(cbor_buffer, cbor_len);
    MQTT_CLIENT.publish("blinds/curtain", cbor_buffer, cbor_len);
  }

  MQTT_CLIENT.loop();
  delay(10);
}
