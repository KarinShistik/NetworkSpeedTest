import socket  # Provides low-level networking interface
import struct  # Helps encode and decode binary data in specific formats
import threading  # Enables the use of multiple threads for concurrent tasks
import time  # Used for delays (e.g., to periodically broadcast)

# Constants defining specific values for packet identification and structure
MAGIC_COOKIE = 0xabcddcba  # Unique identifier to validate packet integrity
OFFER_MSG_TYPE = 0x2  # Indicates the packet is an "offer" from the server
PAYLOAD_MSG_TYPE = 0x4  # Indicates the packet contains file payload


def broadcast_offers(udp_port, tcp_port):
    """
    Periodically sends a broadcast message to let clients know about the server.

    Args:
        udp_port (int): The UDP port clients will use for requests.
        tcp_port (int): The TCP port clients will use for data transfer.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Enable broadcast mode

            while True:
                offer_packet = struct.pack("!IBHH", MAGIC_COOKIE, OFFER_MSG_TYPE, udp_port, tcp_port)
                udp_sock.sendto(offer_packet, ('<broadcast>', 13117))  # Predefined broadcast port
                print("Broadcasted offer packet.")
                time.sleep(1)  # Wait 1 second before sending the next offer
    except Exception as e:
        print(f"Error broadcasting offers: {e}")


def handle_client(client_socket, protocol, udp_address=None, file_size=1_000_000, segment_size=1024):
    """
    Handles communication with a single client.

    Args:
        client_socket (socket.socket): The client's connection socket (TCP only).
        protocol (str): Specifies whether the connection is TCP or UDP.
        udp_address (tuple): The client's address (IP, port) for UDP communication.
        file_size (int): Total file size to transfer in bytes.
        segment_size (int): Size of each segment in bytes for UDP.
    """
    try:
        if protocol == "TCP":
            data = client_socket.recv(1024).decode().strip()
            requested_file_size = int(data)
            print(f"Client requested {requested_file_size} bytes over TCP.")
            client_socket.sendall(b"x" * requested_file_size)
            print("TCP file transfer completed successfully.")

        elif protocol == "UDP" and udp_address:
            total_segments = file_size // segment_size
            print(f"Starting UDP transfer: {total_segments} segments of {segment_size} bytes each.")

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
                for segment_num in range(total_segments):
                    payload_packet = struct.pack(
                        "!IBQQ", MAGIC_COOKIE, PAYLOAD_MSG_TYPE, total_segments, segment_num
                    ) + b"x" * segment_size
                    udp_sock.sendto(payload_packet, udp_address)
                    print(f"Sent UDP segment {segment_num + 1}/{total_segments} to {udp_address}.")

            print(f"UDP transfer to {udp_address} completed.")

    except Exception as e:
        print(f"Error while communicating with client: {e}")
    finally:
        if protocol == "TCP":
            client_socket.close()


def get_server_ip():
    """
    Retrieves the server's local IP address.

    Returns:
        str: Local IP address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp_sock:
            temp_sock.connect(("8.8.8.8", 80))  # Connect to an external address
            return temp_sock.getsockname()[0]
    except Exception as e:
        print(f"Error retrieving server IP: {e}")
        return "127.0.0.1"  # Default to localhost


def main():
    """
    Main function for the server application.
    - Continuously broadcasts offers to clients over UDP.
    - Listens for and handles incoming client connections over TCP.
    """
    udp_port = 0  # Set to 0 to allow dynamic port selection
    tcp_port = 0  # Set to 0 to allow dynamic port selection

    # Get the server's IP address
    server_ip = get_server_ip()
    print(f"Server started, listening on IP address {server_ip}")

    # Create a socket for broadcasting offers
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        udp_sock.bind(('', udp_port))
        udp_port = udp_sock.getsockname()[1]

    # Start broadcasting offers in a separate thread
    threading.Thread(target=broadcast_offers, args=(udp_port, tcp_port), daemon=True).start()

    # Create a socket for TCP communication
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
        tcp_sock.bind(('0.0.0.0', tcp_port))
        tcp_port = tcp_sock.getsockname()[1]
        tcp_sock.listen()  # Start listening for incoming connections
        print(f"Server is running on TCP port {tcp_port}. Waiting for clients...")

        while True:
            client_sock, addr = tcp_sock.accept()
            print(f"Accepted connection from {addr}.")
            threading.Thread(target=handle_client, args=(client_sock, "TCP"), daemon=True).start()


if __name__ == "__main__":
    main()
