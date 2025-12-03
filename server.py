import paho.mqtt.client as mqtt
import cbor2
import hmac
import hashlib

# Shared HMAC key from sketch_dec1a.ino / main.py
HMAC_KEY = bytes.fromhex(
    "71 33 54 02 77 E6 27 8E 0F 52 C3 91 5A 8A AF 74 "
    "AB 56 CE F7 ED 2E 50 91 EC 36 6B E2 B2 F0 71 DC"
)

BROKER_HOST = "10.147.144.34"
BROKER_PORT = 1883

def verify_and_parse_packet(packet_bytes):
    """Verify HMAC-SHA256 and return [type, device_id, timestamp, value]."""
    if len(packet_bytes) < 32:
        print("Packet too short to contain HMAC.")
        return None

    cbor_part = packet_bytes[:-32]
    hmac_part = packet_bytes[-32:]

    computed = hmac.new(HMAC_KEY, cbor_part, hashlib.sha256).digest()
    if not hmac.compare_digest(computed, hmac_part):
        print("HMAC verification failed")
        return None

    print("HMAC Verified")

    try:
        decoded = cbor2.loads(packet_bytes)
    except Exception as e:
        print(f"Error decoding CBOR: {e}")
        return None

    if not isinstance(decoded, list) or len(decoded) != 5:
        print("Unexpected CBOR structure:", decoded)
        return None

    return decoded[:-1]  # [type, device_id, timestamp, value]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe("blinds/temperature")
        client.subscribe("blinds/motion")
        client.subscribe("blinds/door")
        client.subscribe("blinds/curtain")   # ACK/status from ESP
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    print(f"\n--- Message on topic: {msg.topic} ({len(msg.payload)} bytes) ---")
    parsed = verify_and_parse_packet(msg.payload)
    if not parsed:
        return

    msg_type, device_id, timestamp, value = parsed

    print(f"  Device ID: {device_id}")
    print(f"  Timestamp: {timestamp}")

    if msg_type == 1:
        print(f"  Type 1 (Temperature): {value} °C")
    elif msg_type == 2:
        print(f"  Type 2 (Motion): {'Detected' if value else 'No Motion'}")
    elif msg_type == 3:
        print(f"  Type 3 (Door): {'Open' if value else 'Closed'}")
    elif msg_type == 4:
        print(f"  Type 4 (Curtain Position): {value} %")
    else:
        print(f"  Unknown type {msg_type} with value: {value}")

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print(f"Connecting to MQTT broker at {BROKER_HOST}:{BROKER_PORT}...")
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"Failed to run server: {e}")

if __name__ == "__main__":
    main()
