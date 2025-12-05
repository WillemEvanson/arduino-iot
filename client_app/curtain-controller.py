import ssl
import socket
import json
import select
import time
import random
import sys
import os

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

# Add common to import path
common_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'common'))
if common_path not in sys.path:
    sys.path.insert(0, common_path)

from config import *
import project_crypto

def main():
    cloud_socket = project_crypto.construct_ssl_socket(
        True,
        "application",
        "cloud",
        EXTERNAL_CLOUD_IP,
        APPLICATION_PORT
    )

    cloud_websocket = WSConnection(ConnectionType.CLIENT)
    cloud_socket.sendall(cloud_websocket.send(Request(host=EXTERNAL_CLOUD_IP, target = "server")))

    next_curtain = time.time() - 5
    incoming_text = ""
    try:
        while True:
            readable, writable, exceptional = select.select(
                [cloud_socket],
                [],
                [cloud_socket],
                1
            )

            for s in readable:
                in_data = cloud_socket.recv(4096)
                cloud_websocket.receive_data(in_data)

                for event in cloud_websocket.events():
                    if isinstance(event, AcceptConnection):
                        print("Cloud Websocket established")
                        
                        subscriptions = {
                            "subscribe_curtain": True,
                        }
                        message = json.dumps(subscriptions)
                        out_data = cloud_websocket.send(Message(data=message))

                        cloud_socket.sendall(out_data)

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
                            print(incoming_text)
                            incoming_text = ""
                    else:
                        print("Unsupported event: {event!r}")

            if time.time() >= next_curtain:
                message = {"control_curtain": random.randint(0, 100)}
                message = json.dumps(message)
                out_data = cloud_websocket.send(Message(data=message))

                cloud_socket.sendall(out_data)
                next_curtain += 5

    except Exception as e:
        print(f"Failed to run application: {e}")
    
    finally:
        cloud_socket.close()

if __name__ == "__main__":
    main()
