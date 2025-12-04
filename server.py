import paho.mqtt.client as mqtt
import cbor2
import hmac
import hashlib

import json
import select
import time

from wsproto import WSConnection
from wsproto.connection import ConnectionType
from wsproto.events import (
    AcceptConnection,
    RejectConnection,
    CloseConnection,
    Message,
    Ping,
    Pong,
    Request,
    TextMessage,
)

from config import *
import project_crypto

cloud_socket = None
cloud_websocket = None
cloud_data_to_send = []

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

    cloud_data_to_send.append({
        "msg_type": msg_type,
        "device_id": device_id,
        "timestamp": timestamp,
        "value": value,
    })

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    cloud_socket = project_crypto.construct_ssl_socket(
        True,
        "gateway",
        "cloud",
        EXTERNAL_CLOUD_IP,
        GATEWAY_PORT
    )

    cloud_websocket = WSConnection(ConnectionType.CLIENT)
    cloud_socket.sendall(cloud_websocket.send(Request(host=EXTERNAL_CLOUD_IP, target="server")))

    incoming_text = ""
    try:
        print(f"Connecting to MQTT broker at {BROKER_HOST}:{BROKER_PORT}...")
        client.connect(BROKER_HOST, BROKER_PORT, 60)

        while True:
            readable, writable, exceptional = select.select(
                [cloud_socket, client.socket()],
                [cloud_socket],
                [cloud_socket, client.socket()],
                1,
            )

            for socket in readable:
                if socket is cloud_socket:
                    in_data = cloud_socket.recv(4096)
                    cloud_websocket.receive_data(in_data)

                    for event in cloud_websocket.events():
                        if isinstance(event, AcceptConnection):
                            print("Cloud Websocket established")
                        elif isinstance(event, RejectConnection):
                            print("Cloud Websocket rejected")
                            raise Exception("cloud websocket connection rejected")
                        elif isinstance(event, CloseConnection):
                            print("Cloud connection closed: code={} reason={}".format(
                                event.code, event.reason
                            ))
                            cloud_socket.send(cloud_websocket.send(event.response()))
                        elif isinstance(event, Ping):
                            cloud_socket.send(cloud_websocket.send(event.response()))
                        elif isinstance(event, TextMessage):
                            incoming_text += event.data
                            if event.message_finished:
                                message = json.loads(incoming_text)

                                if "control_curtain" in message:
                                    value = message["control_curtain"]
                                    payload = encode_command(1, DEVICE_ID, value)
                                    client.publish("blinds/commands", payload, qos=1)

                                incoming_text = ""
                        else:
                            print("Unsupported event: {event!r}")

                elif socket is client.socket():
                    client.loop_read()
                    client.loop_write()
                    client.loop_misc()

            for socket in writable:
                if socket is cloud_socket and len(cloud_data_to_send) != 0:
                    data = cloud_data_to_send.pop(0)

                    json_string = json.dumps(data)
                    out_data = cloud_websocket.send(Message(data=json_string))

                    cloud_socket.sendall(out_data)


    except Exception as e:
        print(f"Failed to run server: {e}")

    finally:
        cloud_socket.close()

if __name__ == "__main__":
    main()
