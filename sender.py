import paho.mqtt.client as mqtt
import cbor2
import hmac
import hashlib
import time

HMAC_KEY = bytes.fromhex(
    "71 33 54 02 77 E6 27 8E 0F 52 C3 91 5A 8A AF 74 "
    "AB 56 CE F7 ED 2E 50 91 EC 36 6B E2 B2 F0 71 DC"
)

# BROKER_HOST = "10.147.144.34" # Original setting
BROKER_HOST = "localhost"
BROKER_PORT = 1883

def encode_command(cmd_type: int, device_id: str, value: int) -> bytes:
    """
    Create a CBOR command packet with HMAC.
    cmd_type: 1 for curtain command (per existing main.py)
    value: curtain position in [0, 100]
    """
    if not (0 <= value <= 100):
        raise ValueError("Curtain position must be in [0, 100]")

    timestamp = int(time.time())
    empty_hmac = bytes(32)

    array = [cmd_type, device_id, timestamp, value, empty_hmac]
    encoded_without_hmac = cbor2.dumps(array)

    checked_bytes = encoded_without_hmac[:-32]
    mac = hmac.new(HMAC_KEY, checked_bytes, hashlib.sha256).digest()

    full_array = [cmd_type, device_id, timestamp, value, mac]
    return cbor2.dumps(full_array)

def send_curtain_position(position: int, device_id: str = "ESP8266Client"):
    """
    Sends a curtain-position command (TYPE = 1) on blinds/commands.
    ESP receives it in callback(), validates HMAC, clamps to [0,100],
    and publishes blinds/curtain with TYPE = 4.
    """
    payload = encode_command(1, device_id, position)

    client = mqtt.Client()
    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()

        topic = "blinds/commands"
        result = client.publish(topic, payload, qos=1)
        result.wait_for_publish()
        print(f"Published curtain command: {position}% to {topic} ({len(payload)} bytes)")

        time.sleep(0.5)
    except Exception as e:
        print(f"Failed to send command: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    # Sample commands to run...:
    send_curtain_position(100)
    send_curtain_position(50)
    send_curtain_position(0)
