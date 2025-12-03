import paho.mqtt.client as mqtt
import cbor2
import hmac
import hashlib
import time

HMAC_KEY = bytes.fromhex(
    "71 33 54 02 77 E6 27 8E 0F 52 C3 91 5A 8A AF 74 "
    "AB 56 CE F7 ED 2E 50 91 EC 36 6B E2 B2 F0 71 DC"
)

BROKER_HOST = "localhost"
BROKER_PORT = 1883
DEVICE_ID = "ESP8266Client"

def compute_hmac(data: bytes) -> bytes:
    return hmac.new(HMAC_KEY, data, hashlib.sha256).digest()

def verify_packet(data: bytes):
    if len(data) < 32:
        print("Received too-short packet")
        return None

    cbor_part = data[:-32]
    hmac_part = data[-32:]
    computed = compute_hmac(cbor_part)

    if not hmac.compare_digest(computed, hmac_part):
        print("HMAC verification failed (fake_edge)")
        return None

    decoded = cbor2.loads(data)
    if not isinstance(decoded, list) or len(decoded) != 5:
        print("Unexpected CBOR structure:", decoded)
        return None

    msg_type, dev_id, ts, value, _sig = decoded
    return msg_type, dev_id, ts, value

def encode_curtain_status(value: int) -> bytes:
    # Simulate encodeCurtain from the ESP:
    # [4, DEVICE_ID, timestamp, curtain_value, signature]
    value = max(0, min(100, int(value)))  # clamp 0–100
    ts = int(time.time())
    empty_sig = bytes(32)

    arr = [4, DEVICE_ID, ts, value, empty_sig]
    encoded_without_hmac = cbor2.dumps(arr)
    checked_bytes = encoded_without_hmac[:-32]
    mac = compute_hmac(checked_bytes)
    full_arr = [4, DEVICE_ID, ts, value, mac]
    return cbor2.dumps(full_arr)

def on_connect(client, userdata, flags, rc):
    print("fake_edge connected with rc:", rc)
    client.subscribe("blinds/commands")

def on_message(client, userdata, msg):
    print("\n[fake_edge] Message on", msg.topic)
    parsed = verify_packet(msg.payload)
    if not parsed:
        return

    msg_type, dev_id, ts, value = parsed
    print(f"[fake_edge] Command received:")
    print(f"  type: {msg_type}")
    print(f"  device_id: {dev_id}")
    print(f"  timestamp: {ts}")
    print(f"  value: {value}")

    # Only handle type 1 commands (curtain control)
    if msg_type == 1:
        status_payload = encode_curtain_status(value)
        client.publish("blinds/curtain", status_payload, qos=1)
        print(f"[fake_edge] Published curtain status {value}% to blinds/curtain")

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()
