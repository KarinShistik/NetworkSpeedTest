import socket  # Provides low-level networking interface
import struct  # Helps encode and decode binary data in specific formats
import threading  # Enables the use of multiple threads for concurrent tasks
import time  # Used for delays (e.g., to periodically broadcast)

# Constants defining specific values for packet identification and structure
MAGIC_COOKIE = 0xabcddcba  # Unique identifier to validate packet integrity
OFFER_MSG_TYPE = 0x2  # Indicates the packet is an "offer" from the server
PAYLOAD_MSG_TYPE = 0x4  # Indicates the packet contains file payload
BUFFER_SIZE = 1024
BROADCAST_PORT = 13117

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
                udp_sock.sendto(offer_packet, ('<broadcast>', BROADCAST_PORT))  # Predefined broadcast port
                time.sleep(1)  # Wait 1 second before sending the next offer
    except Exception as e:
        print(f"Error broadcasting offers: {e}")


def handle_client(client_socket, protocol, data=10, udp_address=None, segment_size=1024):
    """
    Handles communication with a single client.

    Args:
        client_socket (socket.socket): The client's connection socket (TCP only).
        protocol (str): Specifies whether the connection is TCP or UDP.
        udp_address (tuple): The client's address (IP, port) for UDP communication.
        data (int): Total file size to transfer in bytes.
        segment_size (int): Size of each segment in bytes for UDP.
    """
    try:
        if protocol == "TCP":
            requested_file_size = int(data)
            header = struct.pack("!IBQ", MAGIC_COOKIE, PAYLOAD_MSG_TYPE, requested_file_size)
            payload = b"x" * requested_file_size
            message = header + payload
            client_socket.sendall(message)

        elif protocol == "UDP" and udp_address:
            if data <= segment_size:
                total_segments = 0  # No full segments
                remaining_bytes = data  # The entire data is in one segment
            else:
                total_segments = data // segment_size
                remaining_bytes = data % segment_size

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
                for segment_num in range(total_segments):
                    payload_packet = struct.pack(
                        "!IBQQ", MAGIC_COOKIE, PAYLOAD_MSG_TYPE, total_segments + (1 if remaining_bytes > 0 else 0),
                        segment_num
                    ) + b"x" * segment_size
                    udp_sock.sendto(payload_packet, udp_address)

                if remaining_bytes > 0 or total_segments == 0:
                    segment_num = total_segments  # Use the next segment number
                    payload_packet = struct.pack(
                        "!IBQQ", MAGIC_COOKIE, PAYLOAD_MSG_TYPE, total_segments + 1, segment_num
                    ) + b"x" * remaining_bytes
                    udp_sock.sendto(payload_packet, udp_address)

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
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Create a TCP socket
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Open the socket
    try:
        tcp_sock.bind(('', tcp_port))  # Bind to the selected port
        tcp_sock.listen()
        tcp_port = tcp_sock.getsockname()[1]  # Get the dynamically assigned TCP port

        udp_sock.bind(('0.0.0.0', udp_port))
        udp_port = udp_sock.getsockname()[1]

        # Start broadcasting offers in a separate thread
        threading.Thread(target=broadcast_offers, args=(udp_port, tcp_port), daemon=True).start()
        threads = []

        while True:

            client_sock_tcp, addr_tcp = tcp_sock.accept()
            data = client_sock_tcp.recv(BUFFER_SIZE).decode().strip()
            tcp_thread = threading.Thread(target=handle_client, args=(client_sock_tcp, "TCP", data), daemon=True)
            threads.append(tcp_thread)
            tcp_thread.start()

            data, addr_udp = udp_sock.recvfrom(BUFFER_SIZE)  # Receive data from the client (1024 is the buffer size)
            magic, message_type, file_size = struct.unpack('!IBQ', data)
            udp_thread = threading.Thread(target=handle_client, args=(udp_sock, "UDP", file_size, addr_udp), daemon=True)
            threads.append(udp_thread)
            udp_thread.start()

            # Clean up finished threads
            threads = [t for t in threads if t.is_alive()]

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        if tcp_sock:  # Ensure the socket was created
            tcp_sock.close()
        if udp_sock:  # Ensure the socket was created
            udp_sock.close()


if __name__ == "__main__":
    main()
