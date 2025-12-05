import ssl
import socket
import json
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

    incoming_text = ""
    try:
        while True:
            in_data = cloud_socket.recv(4096)
            cloud_websocket.receive_data(in_data)

            for event in cloud_websocket.events():
                if isinstance(event, AcceptConnection):
                    print("Cloud Websocket established")
                    
                    subscriptions = {
                        "subscribe_temperature": True,
                        "subscribe_motion": True,
                        "subscribe_door": True,
                        "subscribe_curtain": True,
                        "read_motion_history": True,
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
                        if len(incoming_text) >= 1000:
                            message = json.loads(incoming_text)
                            message = json.dumps(message, indent=2)
                        else:
                            message = incoming_text

                        print(message)
                        incoming_text = ""
                else:
                    print("Unsupported event: {event!r}")

    except Exception as e:
        print(f"Failed to run application: {e}")

if __name__ == "__main__":
    main()
