import socket
import threading
import time
import argparse


def udp_sender(send_port: int, target_ip: str, recv_port: int, period: float, message: str, stop_event: threading.Event, broadcast: bool = False) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", send_port))

    # Enable broadcast if requested
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    dest = (target_ip, recv_port)
    count = 0
    while not stop_event.is_set():
        msg = f"{message} [{count}]"
        sock.sendto(msg.encode(), dest)
        print(f"[SEND] {msg} -> {dest}")
        count += 1
        time.sleep(period)
    sock.close()

def udp_receiver(recv_port: int, stop_event: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", recv_port))
    sock.settimeout(0.5)
    while not stop_event.is_set():
        try:
            data, addr = sock.recvfrom(4096)
            print(f"[RECV] {data.decode()} <- {addr}")
        except socket.timeout:
            continue
    sock.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="UDP periodic sender/receiver")
    parser.add_argument("-s", "--send-port", type=int, help="UDP port to send from")
    parser.add_argument("-r", "--recv-port", type=int, help="UDP port to receive on")
    parser.add_argument("-t", "--target-ip", type=str, help="Target IP address to send to (use 255.255.255.255 for broadcast)")
    parser.add_argument("-p", "--period", type=float, default=1.0, help="Send period in seconds")
    parser.add_argument("-m", "--message", type=str, default="Hello, UDP!", help="Message to send")
    parser.add_argument("-b", "--broadcast", action="store_true", help="Enable broadcast mode")
    args = parser.parse_args()

    # Validate arguments
    if args.send_port and not args.target_ip:
        parser.error("--send-port requires --target-ip")
    if not args.send_port and not args.recv_port:
        parser.error("At least one of --send-port or --recv-port must be specified")

    stop_event = threading.Event()
    threads = []

    # Start receiver thread if recv_port is specified
    if args.recv_port:
        receiver_thread = threading.Thread(target=udp_receiver, args=(args.recv_port, stop_event))
        receiver_thread.start()
        threads.append(receiver_thread)

    # Start sender thread if send_port is specified
    if args.send_port:
        # Use recv_port as destination if not specified separately
        dest_port = args.recv_port if args.recv_port else args.send_port
        sender_thread = threading.Thread(target=udp_sender, args=(args.send_port, args.target_ip, dest_port, args.period, args.message, stop_event, args.broadcast))
        sender_thread.start()
        threads.append(sender_thread)

    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping...")
        stop_event.set()
        for thread in threads:
            thread.join()

if __name__ == "__main__":
    main()
