import socket
import ssl

def construct_ssl_socket(is_client, local_name, remote_name, ip, port):
    if is_client:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # Load the local certificates and keys.
    context.load_cert_chain(
        certfile=f"crypto/{local_name}-cert.pem", 
        keyfile=f"crypto/{local_name}-key.pem"
    )
    # Load certificates used for verification.
    context.load_verify_locations(cafile=f"crypto/{remote_name}-cert.pem")
    # Enable mTLS
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if is_client:
        s.connect((ip, port))
        return context.wrap_socket(s)
    else:
        s.bind((ip, port))
        return context.wrap_socket(s, server_side = True)
