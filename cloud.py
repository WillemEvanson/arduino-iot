import socket
import ssl
import select
import json

from wsproto import WSConnection
from wsproto.connection import ConnectionType
from wsproto.events import (
    AcceptConnection,
    CloseConnection,
    Message,
    Ping,
    Pong,
    Request,
    TextMessage,
)

from common.config import *
from common import project_crypto

def main():
    temperature_history = open('temperature_history.txt', 'a+')
    motion_history = open('motion_history.txt', 'a+')
    door_history = open('door_history.txt', 'a+')
    curtain_history = open('curtain_history.txt', 'a+')

    gateway_listener = project_crypto.construct_ssl_socket(
        False,
        "cloud",
        "gateway",
        INTERNAL_CLOUD_IP,
        GATEWAY_PORT
    )

    print(f"Listening for gateway on {GATEWAY_PORT}")
    gateway_listener.listen()
    gateway, gateway_address = gateway_listener.accept()

    print(f"Gateway connected at {gateway_address[0]}:{gateway_address[1]}")

    gateway_ws = WSConnection(ConnectionType.SERVER)

    application_listener = project_crypto.construct_ssl_socket(
        False,
        "cloud",
        "application",
        INTERNAL_CLOUD_IP,
        APPLICATION_PORT
    )

    application_listener.listen()

    cloud_websocket_message = ""

    applications = dict()

    temperature_listeners = set()
    motion_listeners = set()
    door_listeners = set()
    curtain_listeners = set()

    new_temperature_data = []
    new_motion_data = []
    new_door_data = []
    new_curtain_data = []
    try:
        while True:
            listened_sockets = [gateway, application_listener] + list(applications.keys())
            readable, writable, exceptional = select.select(
                listened_sockets,
                [],
                listened_sockets,
                1
            )

            for socket in readable:
                if socket is gateway:
                    in_data = gateway.recv(4096)
                    gateway_ws.receive_data(in_data)

                    out_data = b""
                    for event in gateway_ws.events():
                        if isinstance(event, Request):
                            print("Gateway: Accepting WebSocket Connection")
                            out_data += gateway_ws.send(AcceptConnection())
                        elif isinstance(event, CloseConnection):
                            print("Gateway: Connection closed")
                            out_data += gateway_ws.send(event.response())
                        elif isinstance(event, TextMessage):
                            print(f"Received Text Message: {event.data}")
                            cloud_websocket_message += event.data
                            if event.message_finished:
                                # Handle complete JSON message
                                message = json.loads(cloud_websocket_message)
                                
                                if message["msg_type"] == 1:
                                    file = temperature_history
                                    new_data = new_temperature_data
                                elif message["msg_type"] == 2:
                                    file = motion_history
                                    new_data = new_motion_data
                                elif message["msg_type"] == 3:
                                    file = door_history
                                    new_data = new_door_data
                                elif message["msg_type"] == 4:
                                    file = curtain_history
                                    new_data = new_curtain_data
                                
                                device_id = message["device_id"]
                                timestamp = message["timestamp"]
                                value = message["value"]

                                file.write(f"{cloud_websocket_message}\n")
                                file.flush()
                                new_data.append(message)
                                
                                # Clear stored message to prepare to next potentially fragmented message.
                                cloud_websocket_message = ""
                        else:
                            print(f"Unknown event: {event!r}")

                    gateway.sendall(out_data)
                    continue

                elif socket is application_listener:
                    application, application_address = application_listener.accept()
                    print(f"Application connected from {application_address[0]}:{application_address[1]}")

                    applications[application] = (WSConnection(ConnectionType.SERVER), "")
                    continue

                # Socket must be an application socket.
                try:
                    application_socket = socket
                    application_websocket, application_data = applications[socket]
                    in_data = application_socket.recv(4096)
                    application_websocket.receive_data(in_data)

                    out_data = b""
                    for event in application_websocket.events():
                        if isinstance(event, Request):
                            print("Application: Accepting WebSocket Connection")
                            out_data += application_websocket.send(AcceptConnection())
                        elif isinstance(event, CloseConnection):
                            print("Application: Connection closed")
                            out_data += application_websocket.send(event.response())
                        elif isinstance(event, TextMessage):
                            print(f"Application: Received Text Message: {event.data}")
                            application_data += format(event.data)
                            if event.message_finished:
                                print(application_data)
                                message = json.loads(application_data)
                                
                                if "subscribe_temperature" in message:
                                    if message["subscribe_temperature"]:
                                        temperature_listeners.add(application_socket)
                                    else:
                                        temperature_listeners.discard(application_socket)
                                if "subscribe_motion" in message:
                                    if message["subscribe_motion"]:
                                        motion_listeners.add(application_socket)
                                    else:
                                        motion_listeners.discard(application_socket)
                                if "subscribe_door" in message:
                                    if message["subscribe_door"]:
                                        door_listeners.add(application_socket)
                                    else:
                                        door_listeners.discard(application_socket)
                                if "subscribe_curtain" in message:
                                    if message["subscribe_curtain"]:
                                        curtain_listeners.add(application_socket)
                                    else:
                                        curtain_listeners.discard(application_socket)

                                if "read_temperature_history" in message and message["read_temperature_history"]:
                                    temperature_history.seek(0)
                                    history = temperature_history.read()
                                    temperature_history.seek(0, 2)

                                    history = list(map(lambda s: json.loads(s), history.splitlines()))

                                    history_message = {"temperature_history": history}
                                    history_message = json.dumps(history_message)
                                    out_data += application_websocket.send(Message(data=history_message))

                                if "read_motion_history" in message and message["read_motion_history"]:
                                    motion_history.seek(0)
                                    history = motion_history.read()
                                    motion_history.seek(0, 2)

                                    history = list(map(lambda s: json.loads(s), history.splitlines()))

                                    history_message = {"motion_history": history}
                                    history_message = json.dumps(history_message)
                                    out_data += application_websocket.send(Message(data=history_message))

                                if "read_door_history" in message and message["read_door_history"]:
                                    door_history.seek(0)
                                    history = door_history.read()
                                    door_history.seek(0, 2)

                                    history = list(map(lambda s: json.loads(s), history.splitlines()))

                                    history_message = {"door_history": history}
                                    history_message = json.dumps(history_message)
                                    out_data += application_websocket.send(Message(data=history_message))

                                if "read_curtain_history" in message and message["read_curtain_history"]:
                                    curtain_history.seek(0)
                                    history = curtain_history.read()
                                    curtain_history.seek(0, 2)

                                    history = list(map(lambda s: json.loads(s), history.splitlines()))

                                    history_message = {"curtain_history": history}
                                    history_message = json.dumps(history_message)
                                    out_data += application_websocket.send(Message(data=history_message))

                                if "control_curtain" in message:
                                    value = message["control_curtain"]

                                    gateway_message = {"control_curtain": value}
                                    gateway_message = json.dumps(message)
                                    gateway_out_data = gateway_ws.send(Message(data=gateway_message))

                                    gateway.sendall(gateway_out_data)

                                # Clear stored message to prepare to next potentially fragmented message.
                                application_data = ""
                                    
                        else:
                            print("Application: Unknown event: {event!r}")

                    application_socket.sendall(out_data)
                except Exception as e:
                    print(f"Application Exception: {e}")

                    del applications[socket]

                    temperature_listeners.discard(socket)
                    motion_listeners.discard(socket)
                    door_listeners.discard(socket)
                    curtain_listeners.discard(socket)

            listeners_list = [temperature_listeners, motion_listeners, door_listeners, curtain_listeners]
            new_data_list = [new_temperature_data, new_motion_data, new_door_data, new_curtain_data]

            # Dead sockets is used because modification of the length of an iterator during iteration triggers an exception.
            dead_sockets = set()
            for listeners, new_data in zip(listeners_list, new_data_list):
                for listener_socket in listeners:
                    try:
                        listener_websocket, incoming_data = applications[listener_socket]
                        for data in new_data:
                            json_string = json.dumps(message)
                            out_data = listener_websocket.send(Message(data=json_string))
                            listener_socket.sendall(out_data)
                    except Exception as e:
                        if listener_socket not in dead_sockets:
                            print(f"Application Exception: {e}")

                            del applications[listener_socket]
                            dead_sockets.add(listener_socket)

            # Remove any dead sockets from the listener sets.
            temperature_listeners -= dead_sockets
            motion_listeners -= dead_sockets
            door_listeners -= dead_sockets
            curtain_listeners -= dead_sockets

            new_temperature_data = []
            new_motion_data = []
            new_door_data = []
            new_curtain_data = []

    finally:
        gateway.close()
        gateway_listener.close()
        application_listener.close()

        for application_socket in applications.keys():
            application_socket.close()

        temperature_history.close()
        motion_history.close()
        door_history.close()
        curtain_history.close()

if __name__ == "__main__":
    main()
