import paho.mqtt.client as mqtt
import cbor2
import hmac
import hashlib
import time

HMAC_KEY = bytes.fromhex("71 33 54 02 77 E6 27 8E 0F 52 C3 91 5A 8A AF 74 AB 56 CE F7 ED 2E 50 91 EC 36 6B E2 B2 F0 71 DC")

def encode_command(cmd_type: int, device_id: str, value: int):
    if not (0 <= value <= 100):
        raise ValueError("value must be in [0, 100]")

    timestamp = int(time.time())

    # Set up the packet without the HMAC
    empty_hmac = bytes(32)
    array = [cmd_type, device_id, timestamp, value, empty_hmac]
    encoded_without_hmac = cbor2.dumps(array)

    checked_bytes = encoded_without_hmac[:-32]

    # Create the HMAC and the new message
    mac = hmac.new(HMAC_KEY, checked_bytes, hashlib.sha256).digest()
    full_array = [cmd_type, device_id, timestamp, value, mac]

    return cbor2.dumps(full_array)

def send_blinds_position(client, device_id: str, position: int):
    payload = encode_command(1, device_id, position)
    client.publish("blinds/commands", payload, qos=1)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code: ", rc);
    client.subscribe("blinds/temperature")
    client.subscribe("blinds/door")
    client.subscribe("blinds/motion")

    client.subscribe("blinds/curtain")

def on_message(client, userdata, msg):
    data = msg.payload
    if len(data) < 32:
        print("Invalid message")
        return

    cbor_part = data[:-32]
    hmac_part = data[-32:]
    computed = hmac.new(HMAC_KEY, cbor_part, hashlib.sha256).digest()
    if not hmac.compare_digest(computed, hmac_part):
        print("HMAC verification failed")
        return

    message = cbor2.loads(data)
    print("Received: ", message)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("laptop.local", 1883, 60)

send_blinds_position(client, "ESP8266Client", 100)
send_blinds_position(client, "ESP8266Client", 50)
send_blinds_position(client, "ESP8266Client", 0)
client.loop_forever()
