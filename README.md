## IoT Curtain Control System (Cloud & Edge)

This repository contains the code for our secure IoT curtain control system, which includes both the **edge device firmware** and the **cloud-side monitoring and control applications**.

-----

## Project Structure & Key Files

The project is split into two main components:

| File/Folder | Purpose | Languages |
| :--- | :--- | :--- |
| `sketch_dec1a/` | **ESP8266 Firmware Source.** Contains the Arduino sketch (`.ino`) with CBOR encoding, HMAC, MQTT logic, and hardware control. | C++ |
| `edge.txt` | **Project Specification.** Defines the Packet Format, HMAC rules, and MQTT Topics. | Text |
| `server.py` | **Cloud Receiver & Verifier.** Monitors device telemetry and verifies security. | Python |
| `sender.py` | **Cloud Command Publisher.** Generates secure commands to control the curtain. | Python |
| `fake_edge.py` | **Software Simulator.** Allows full local testing without physical hardware. | Python |
| `main.py` | **Reference Implementation.** Team's validated code for CBOR/HMAC logic. | Python |

-----

## Shared Security: HMAC-SHA256

All components (firmware and cloud applications) enforce security by sharing the identical 32-byte HMAC key and following the same packet signing/verification procedure.

The HMAC is computed over **all encoded CBOR bytes except the final 32-byte signature field** (`buf[0 : array_end - 32]`).

```python
HMAC_KEY = bytes.fromhex(
    "71 33 54 02 77 E6 27 8E 0F 52 C3 91 5A 8A AF 74 "
    "AB 56 CE F7 ED 2E 50 91 EC 36 6B E2 B2 F0 71 DC"
)
```

## Cloud Component Documentation

### 1\. `server.py` – Cloud Monitor & Verifier

Functions as the primary cloud monitoring service. It:

  * Subscribes to all device telemetry topics (`blinds/temperature`, `blinds/motion`, `blinds/door`, `blinds/curtain`).
  * Verifies the HMAC-SHA256 signature on every incoming packet.
  * Decodes the CBOR array structure: `[type, device_id, timestamp, value, signature]`.
  * Interprets and prints human-readable sensor and status updates (Types 1–4).

### 2\. `sender.py` – Cloud Command Publisher

Used to send control commands securely from the cloud to the device. It:

  * Constructs a CBOR control packet (using **Type 1** for curtain commands).
  * Applies a secure HMAC-SHA256 signature.
  * Publishes the signed command packet to the control topic: `blinds/commands`.

### 3\. `fake_edge.py` – Software Simulator

A utility to test the full cloud pipeline locally without the physical ESP8266 hardware. It:

  * Subscribes to `blinds/commands` to mimic the ESP's reception.
  * Verifies the incoming packet's HMAC.
  * Publishes a simulated **Curtain Status (Type 4)** packet on `blinds/curtain` as a command acknowledgment.

-----

## Setup & Run Instructions

### Prerequisites

1.  **MQTT Broker:** Install **Mosquitto** (`brew install mosquitto` on macOS).
2.  **Python Libraries:** Set up a virtual environment and install dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install paho-mqtt cbor2
    ```

### Running the Cloud Simulation (Localhost)

This setup uses `localhost` for testing `server.py` and `sender.py` against the `fake_edge.py` simulator.

1.  **Start Mosquitto Broker** (Terminal 1)
    ```bash
    mosquitto -v
    ```
2.  **Start Cloud Monitor** (`server.py`) (Terminal 2)
    ```bash
    source venv/bin/activate
    python server.py
    ```
3.  **Start Edge Simulator** (`fake_edge.py`) (Terminal 3)
    ```bash
    source venv/bin/activate
    python fake_edge.py
    ```
4.  **Send Cloud Commands** (`sender.py`) (Terminal 4)
    ```bash
    source venv/bin/activate
    python sender.py
    ```
    *Observation:* The commands will flow from `sender.py` $\rightarrow$ `fake_edge.py` $\rightarrow$ `server.py`, with *server.py* confirming "HMAC Verified" on the final status message.

### Integrating with the Real ESP8266

To connect the real device, you must ensure the **broker IP address is consistent everywhere**:

1.  **Determine Broker Host IP:** Find the actual IP address of the machine running Mosquitto (e.g., `10.147.144.34`).
2.  **Update ESP Firmware:** Change `MQTT_SERVER_NAME` in `sketch_dec1a/sketch_dec1a.ino` to the real IP (e.g., `"10.147.144.34"`).
3.  **Update Python Scripts:** Change `BROKER_HOST` in `server.py`, `sender.py`, and `fake_edge.py` to the real IP.
