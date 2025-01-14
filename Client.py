import socket
import struct
import threading
import time

MAGIC_COOKIE = 0xabcddcba
OFFER_MSG_TYPE = 0x2
REQUEST_MSG_TYPE = 0x3
PAYLOAD_MSG_TYPE = 0x4
BROADCAST_PORT = 13117
BUFFER_SIZE = 1024


def listen_for_offers(server_info):
    """
    Listens for server broadcast offers and updates the server_info dictionary.
    Args:
        server_info (dict): A shared dictionary to store the server's IP, UDP port, and TCP port.
    Behavior:
        - Binds to a UDP broadcast port and waits for server offer packets.
        - Validates received packets using `MAGIC_COOKIE` and `OFFER_MSG_TYPE`.
        - Updates `server_info` with server details upon receiving a valid packet.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(('', BROADCAST_PORT))  # Bind to the broadcast port
        print("Client started, listening for offer requests...")
        while True:
            data, addr = udp_sock.recvfrom(BUFFER_SIZE)
            magic, msg_type, udp_port, tcp_port = struct.unpack("!IBHH", data)

            if magic == MAGIC_COOKIE and msg_type == OFFER_MSG_TYPE:
                server_ip = addr[0]
                server_info['address'] = server_ip
                server_info['udp_port'] = udp_port
                server_info['tcp_port'] = tcp_port
                print(f"Received offer from {server_ip}")  # Log the received offer
                break


def tcp_download(server_ip, tcp_port, file_size, conn_id):
    """
    Handles file download using TCP and measures transfer speed.
    Args:
        server_ip (str): The server's IP address.
        tcp_port (int): The server's TCP port.
        file_size (int): The size of the file to download in bytes.
        conn_id (int): A unique connection ID for identifying the transfer.
    Behavior:
        - Establishes a TCP connection to the server.
        - Sends the requested file size to the server.
        - Receives data in chunks until the requested file size is reached.
        - Calculates and logs the total transfer time and speed.
    """
    try:
        with socket.create_connection((server_ip, tcp_port)) as sock:
            sock.sendall(f"{file_size}\n".encode())
            start_time = time.time()
            received_data = 0
            while received_data < file_size:
                data = sock.recv(BUFFER_SIZE)
                magic, msg_type, file_len = struct.unpack("!IBQ", data[:13])
                if not data:
                    break
                received_data += len(data)

            elapsed_time = time.time() - start_time
            speed = (received_data * 8) / elapsed_time  # bits per second
            print(f"TCP transfer #{conn_id} finished, total time: {elapsed_time:.2f} seconds, total speed: {speed:.2f} bits/second")
    except Exception as e:
        print(f"Error in TCP connection #{conn_id}: {e}")


def udp_download(server_ip, udp_port, file_size, conn_id):
    """
    Handles file download using UDP and measures transfer speed.
    Args:
        server_ip (str): The server's IP address.
        udp_port (int): The server's UDP port.
        file_size (int): The size of the file to download in bytes.
        conn_id (int): A unique connection ID for identifying the transfer.
    Behavior:
        - Sends a file request packet to the server with the specified file size.
        - Receives data packets from the server, validating their headers.
        - Tracks received data, discarded packets, and calculates packet loss percentage.
        - Logs total time, transfer speed, and packet success percentage.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1)
            request_packet = struct.pack("!IBQ", MAGIC_COOKIE, REQUEST_MSG_TYPE, file_size)
            sock.sendto(request_packet, (server_ip, udp_port))

            start_time = time.time()
            received_data = 0
            discarded_packets = 0
            total_segments = 0
            while True:
                try:
                    data, _ = sock.recvfrom(BUFFER_SIZE*2)
                    magic, msg_type, total_segments, current_segment = struct.unpack("!IBQQ", data[:21])
                    if magic != MAGIC_COOKIE or msg_type != PAYLOAD_MSG_TYPE:
                        discarded_packets += 1
                        continue
                    received_data += len(data)  # Subtract header size
                except socket.timeout:
                    break

            elapsed_time = time.time() - start_time
            speed = (received_data * 8) / elapsed_time  # bits per second
            loss_percentage = 100 - ((total_segments - discarded_packets) / (total_segments or 1)) * 100
            print(f"UDP transfer #{conn_id} finished, total time: {elapsed_time:.2f} seconds, total speed: {speed:.2f} bits/second, "
                  f"percentage of packets received successfully: {100 - loss_percentage:.2f}%")
    except Exception as e:
        print(f"Error in UDP connection #{conn_id}: {e}")


def get_file_size():
    """
    Prompts the user to enter a file size and its unit, then converts it to bytes.
    Returns:
        int: The file size in bytes.
    Behavior:
        - Prompts the user for the file size (numeric) and unit (GB, MB, KB, or B).
        - Validates input and converts the size to bytes using a unit map.
    """
    unit_map = {
        "GB": 1e9,
        "MB": 1e6,
        "KB": 1e3,
        "B": 1
    }

    while True:
        try:
            # Prompt user for file size
            size = input("Enter the file size to download: ").strip()
            if not size.replace('.', '', 1).isdigit():
                raise ValueError("Invalid size. Please enter a numeric value.")
            size = float(size)

            # Prompt user for unit
            unit = input("Enter the unit (GB, MB, KB, or B): ").strip().upper()
            if unit not in unit_map:
                raise ValueError("Invalid unit. Please enter GB, MB, KB, or B.")

            # Return file size in bytes
            return int(size * unit_map[unit])

        except ValueError as e:
            print(f"Error: {e}")
            print("Please try again.")


def main():
    """
    Client for link-speed measuring program.
    Behavior:
        - Prompts the user for file size, number of TCP connections, and UDP connections.
        - Calls `listen_for_offers` to find a server and gather its connection details.
        - Spawns threads to handle TCP and UDP downloads based on user input.
        - Waits for all threads to complete and logs transfer results.
    """
    while True:
        # Phase 1: Startup
        file_size = get_file_size()
        tcp_connections = int(input("Enter the number of TCP connections: "))
        udp_connections = int(input("Enter the number of UDP connections: "))

        # Phase 2: Looking for a server
        server_info = {}
        listen_for_offers(server_info)

        if not server_info:
            print("No server found. Exiting.")
            return

        server_ip = server_info['address']
        udp_port = server_info['udp_port']
        tcp_port = server_info['tcp_port']

        # Phase 3: Speed Test
        threads = []

        for i in range(1, tcp_connections + 1):
            t = threading.Thread(target=tcp_download, args=(server_ip, tcp_port, file_size, i))
            threads.append(t)
            t.start()

        for i in range(1, udp_connections + 1):
            t = threading.Thread(target=udp_download, args=(server_ip, udp_port, file_size, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        print("All transfers complete, listening to offer requests")


if __name__ == "__main__":
    main()
