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

from config import *
import project_crypto


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
    try:
        while True:
            readable, writable, exceptional = select.select(
                [gateway, application_listener],
                [],
                [gateway, application_listener],
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
                                elif message["msg_type"] == 2:
                                    file = motion_history
                                elif message["msg_type"] == 3:
                                    file = door_history
                                elif message["msg_type"] == 4:
                                    file = curtain_history
                                
                                device_id = message["device_id"]
                                timestamp = message["timestamp"]
                                value = message["value"]

                                file.write(f"{device_id} at {timestamp}: {value}\n")

                                cloud_websocket_message = ""
                        else:
                            print(f"Unknown event: {event!r}")

                    gateway.sendall(out_data)

    except Exception as e:
        print(f"Fatal exception: {e}")

    finally:
        gateway.close()
        gateway_listener.close()
        application_listener.close()

        temperature_history.close()
        motion_history.close()
        door_history.close()
        curtain_history.close()


    """
    application_listener = project_crypto.construct_ssl_socket(
        False,
        "cloud",
        "application",
        HOST,
        APPLICATION_PORT
    )

    application_listener.listen()


    incoming_gateway = project_crypto.construct_ssl_socket(
        False,
        "cloud",
        "gateway",
        HOST,
        GATEWAY_PORT
    )
    incoming_applications = project_crypto.construct_ssl_socket(
        False,
        "cloud",
        "application",
        HOST,
        APPLICATION_PORT
    )

    incoming_gateway.listen()
    incoming_applications.listen()

    active_sockets = [incoming_gateway, incoming_applications]
    gateways = dict()
    applications = dict()

    print(f"Server now listening on {HOST} at {GATEWAY_PORT} and {APPLICATION_PORT}")
    try:
        while active_sockets:
            readable, writable, exceptional = select.select(
                active_sockets, # Sockets to be monitored for readability
                [], # Sockets to be monitored for writability (we don't carry about that)
                active_sockets, # Sockets to be monitored for exceptional conditions
                1 # The timeout
            )

            for s in readable:
                try:
                    if s is incoming_gateway:
                        conn, addr = s.accept()

                        active_sockets.append(conn)
                        print(f"Accepted gateway connection from {addr}")

                    elif s is incoming_applications:
                        socket, addr = s.accept()

                        config = h2.config.H2Configuration(client_side=False)
                        connection = h2.connection.H2Connection(config=config)

                        connection.initiate_connection()
                        socket.sendall(connection.data_to_send())

                        active_sockets.append(socket)
                        applications[socket] = connection
                        print(f"Accepted application connection from {addr}")

                    elif s in gateways:
                        # Handle incoming gateway data
                        1 + 1

                    elif s in applications:
                        application_connection = applications[s]

                        # Handle incoming application requests
                        data = s.recv(65535)
                        if not data:
                            break

                        events = application_connection.receive_data(data)
                        for event in events:
                            print(event)
                            if isinstance(event, h2.events.RequestReceived):
                                1 + 1

                except Exception as e:
                    print(f"Handling exception: {e}")
                    if s in gateways:
                        del gateways[s]
                    elif s in applications:
                        del applications[s]

                    if s is not incoming_gateway and s is not incoming_applications:
                        active_sockets.remove(s)
                        s.close()

            for s in exceptional:
                print(f"Handling exceptional condition for {s.getpeername()}")
                active_sockets.remove(s)
                s.close()

    
    except Exception as e:
        print(f"Fatal exception: {e}")

    finally:
        incoming_gateway.close()
        incoming_applications.close()
    """


if __name__ == "__main__":
    main()
