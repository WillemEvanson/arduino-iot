import paho.mqtt.client as mqtt
import cbor2
import hmac
import hashlib
import time
import random
import sys
import os

# Add common to import path
common_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'common'))
if common_path not in sys.path:
    sys.path.insert(0, common_path)

from config import *

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

def encode_packet(kind: int, value):
    ts = int(time.time())
    empty_sig = bytes(32)

    arr = [kind, DEVICE_ID, ts, value, empty_sig]
    encoded_without_hmac = cbor2.dumps(arr)
    checked_bytes = encoded_without_hmac[:-32]
    mac = compute_hmac(checked_bytes)
    full_arr = [kind, DEVICE_ID, ts, value, mac]
    return cbor2.dumps(full_arr)

def encode_temperature(value: int) -> bytes:
    return encode_packet(1, value)

def encode_motion(value: bool) -> bytes:
    return encode_packet(2, value)

def encode_door(value: bool) -> bytes:
    return encode_packet(3, value)

def encode_curtain_status(value: int) -> bytes:
    value = max(0, min(100, int(value)))  # clamp 0–100
    return encode_packet(4, value)

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

    next_packet = time.time()
    next_check = time.time()
    while True:
        t = time.time()
        if t >= next_packet:
            next_packet += 0.5

            selection = random.randint(1, 4)

            if selection == 1:
                packet = encode_temperature(random.randint(50, 100))
                category = "blinds/temperature"
            elif selection == 2:
                packet = encode_motion(random.choice([True, False]))
                category = "blinds/motion"
            else:
                packet = encode_door(random.choice([True, False]))
                category = "blinds/door"

            client.publish(category, packet, qos=1)
        if t >= next_check:
            next_check += 0.1

            client.loop_read()
            client.loop_write()
            client.loop_misc()

if __name__ == "__main__":
    main()
