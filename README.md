## IoT Curtain Control System

This repository contains the secure IoT curtain control system, which includes a:
* Edge device (Arduino/ESP8266) simulating sensing and curtain control.
* Gateway server for MQTT translation and cloud communication.
* Cloud server for secure data storage, command authentication, and historical telemetry access.

-----

## Project Structure & Key Files

The project is split into a few main components:

| File/Folder | Purpose | Languages |
| :--- | :--- | :--- |
| `sketch_dec1a/` | **ESP8266 Firmware Source.** Contains the Arduino sketch (`.ino`) with CBOR encoding, HMAC, MQTT logic, and hardware control. | C++ |
| `gateway.py` | **Gateway Hub.** Monitors device telemetry and moves packets between MQTT broker and cloud. | Python |
| `cloud.py` | **Cloud.** Receives and stores device telemetry. Forwards authenticated commands to gateway service. Grants access to historical telemetry data. | Python |
| `client_app/curtain-controller.py` | **Cloud Command Publisher.** Generates secure commands to control the curtain. | Python |
| `client_app/watcher.py` | **Cloud Command Publisher.** Displays the data received by the cloud server. | Python |
| `testing/fake_edge.py` | **Software Simulator.** Allows full local testing without physical hardware. | Python |

-----

## Environment Setup

### Arduino / ESP8266

1. **Install Arduino IDE:** [Arduino IDE Download](https://www.arduino.cc/en/software/#ide)
2. **Prepare For Flashing:** [Arduino IDE Setup](http://www.hiletgo.com/ProductDetail/1906570.html)
3. **Add Required Libraries:**
   * ArduinoBearSSL
   * ArduinoECCX08
   * PubSubClient
   * TinyCBOR
4. **Serial Port (Linux):** Add your user account to the `dialout` group. You may need to
logout for it to take effect. The serial port is usually `/dev/ttyUSB*`.
5. **Wi-Fi Setup:**
   * Set `WIFI_SSID` and `WIFI_PASSWORD` in the Arduino sketch.
   * Ensure DHCP assigns a valid IP.
6. **MQTT Setup:**
   * Broker Host: Set `MQTT_SERVER_NAME` to the DNS name. This is currently `laptop.local`.
   * TLS: Copy the CA certificate into the `ca_cert` variable.
   * HMAC: Generate a set of 32+ random bytes. Put these bytes into `HMAC_KEY`.
7. **Flash the Firmware:** Press the `Upload` button.

### Gateway (MQTT Broker)
1. **Install Mosquitto:** The MQTT broker is used to bridge communications between the Arduino
and the Python gateway.
2. **Prepare for Key Creation:** Create `server.ext` with the following text. Change `laptop.local`
to the DNS address of the gateway.
```text
basicConstraints = critical,CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:laptop.local
```
3. **Create the CA Certificate & Keys:** This will create the necessary keys for a private CA
and a server certificate that can handle TLS.
```bash
openssl ecparam -genkey -name prime256v1 -out ca.key
openssl req -x509 -new nodes -key ca.key -sha256 -days 365 -out ca.crt

openssl ecparam -genkey -name prime256v1 -out server.key
openssl req -new -key server.key -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365 -sha256 -extfile server.ext
```
4. **Finish Setup:** Move the key files to a protected directory and put the following into
the Mosquitto configuration file.
```ini
# Arduino - MQTT Broker
listener 8883
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
allow_anonymous true
tls_version tlsv1.2

# MQTT Broker - Gateway Service
listener 1883 127.0.0.1
allow_anonymous true
```

### Python Environment (Gateway & Cloud)

1. **Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```
2. **Install dependencies:**
```bash
pip install paho-mqtt cbor2 wsproto
```

3. **Update Configuration:** Update the parameters in `common/config.py`.
   * Update `HMAC_KEY` to the Arduino's `HMAC_KEY`.
   * Update `INTERNAL_CLOUD_IP` and `EXTERNAL_CLOUD_IP` to the IP address's seen
   within the cloud.
   * Update `GATEWAY_PORT` and `APPLICATION_PORT` if necessary.

3. **Install Certificates:** Place the TLS/mTLS certificates in a folder and update `gateway.py`
and `cloud.py` paths accordingly.

4. **Run Gateway / Cloud**
```bash
# Gateway
python server.py

# Cloud
python cloud.py
```
---

## Client Applications

### 1\. `client_app/curtain_controller.py` - Cloud Command Publisher
* Randomly generates curtain values and sends them to the cloud.
* Used for demonstrating curtain and command handling.

### 2\. `client_app/watcher.py` - Cloud Monitor
* Can subscribe to all device telemetry topics (`blinds/temperature`, `blinds/motion`, `blinds/door`, `blinds/curtain`).
* Can download historical data from the cloud server and display it.

### 3\. `testing/fake_edge.py` - Software Simulator
* Simulates much of the functionality of the Arduino.
* Used to test the other components without access to the Arduino.

---

## Module Descriptions

### Arduino Sensor Node

**Objective:** Acts as the edge device providing sensor readings and receiving curtain commands.

**Hardware:** Arduino/ESP8266 board with Wi-Fi.

**Simulated / Real Data:**

- Temperature (random or real)
- Motion detected (random or real)
- Door open/closed state (random or real)
- Curtain position (0–100%)

**Libraries Required:**

- ArduinoBearSSL – TLS and HMAC
- ArduinoECCX08 – optional hardware crypto
- PubSubClient – MQTT
- TinyCBOR – CBOR encoding

**Security:**

- TLS server certificate to connect to the gateway.
- HMAC-SHA256 appended to each MQTT message with a pre-shared key (PSK).

---

### Gateway Server

**Objective:** Handles secure communication between the Arduino and the cloud.

**Hardware:** Laptop or local server.

**Functions:**

- MQTT broker (Mosquitto) for Arduino communication.
- HMAC verification and message rejection if invalid.
- Translation of MQTT messages to JSON.
- Forwarding data to the cloud via WebSockets with mTLS.
- Receiving cloud commands and publishing to Arduino via MQTT.

**Libraries:**

- `ssl` – mTLS
- `json` – encoding/decoding
- `wsproto` – WebSockets communication
- `paho-mqtt` – MQTT communication
- `cbor2` – decoding/encoding MQTT messages
- `hmac` – SHA-256 HMAC verification

**Security:**

- TLS server certificate for encrypted Arduino connection.
- HMAC-SHA256 for message integrity.
- mTLS for cloud-gateway communication.

---

### Cloud Server

**Objective:** Central secure storage and control.

**Hardware:** Cloud server (e.g., Oracle Cloud Free Tier).

**Functions:**

- Receive and store telemetry from the gateway.
- Authenticate clients and retrieve historical data.
- Relay authenticated commands to Arduino via gateway.

**Communication:** WebSockets with mTLS.

**Libraries:**

- `ssl` – mTLS
- `json` – encoding/decoding
- `wsproto` – WebSockets communication
- `hmac` – SHA-256 HMAC verification

**Security:**

- mTLS for all connections.
- Authorization checks before relaying commands.