import socket
import threading
import time
import argparse
import sys
from typing import List, Tuple, Optional
try:
    import netifaces
except ImportError:
    print("The 'netifaces' package is required. Please install it with 'pip install netifaces'.")
    sys.exit(1)


def get_broadcast_addresses(interface_names: List[str]) -> List[Tuple[str, str]]:
    addrs: List[Tuple[str, str]] = []
    for iface in interface_names:
        if iface not in netifaces.interfaces():
            print(f"Warning: Interface '{iface}' not found.")
            continue
        iface_addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in iface_addrs:
            for addr in iface_addrs[netifaces.AF_INET]:
                bcast = addr.get('broadcast')
                if bcast:
                    addrs.append((bcast, iface))
    return addrs

def udp_sender(
    target_ip: str,
    dest_port: int,
    period: float,
    message: str,
    stop_event: threading.Event,
    broadcast: bool = False,
    broadcast_ifaces: Optional[List[str]] = None
) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Let the OS choose the source port

    count = 0
    if broadcast and broadcast_ifaces:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        bcast_addrs = get_broadcast_addresses(broadcast_ifaces or [])
        if not bcast_addrs:
            print("No valid broadcast addresses found for specified interfaces.")
            return
        while not stop_event.is_set():
            msg = f"{message} [{count}]"
            for bcast, iface in bcast_addrs:
                dest = (bcast, dest_port)
                sock.sendto(msg.encode(), dest)
                print(f"[BROADCAST] {msg} -> {dest} on {iface}")
            count += 1
            time.sleep(period)
    else:
        dest = (target_ip, dest_port)
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
    parser.add_argument("-r", "--recv-port", type=int, help="Local port to receive on")
    parser.add_argument("-d", "--dest-port", type=int, help="Destination port to send to")
    parser.add_argument("-t", "--target-ip", type=str, help="Target IP address to send to (ignored in broadcast mode)")
    parser.add_argument("-p", "--period", type=float, default=1.0, help="Send period in seconds")
    parser.add_argument("-m", "--message", type=str, default="Hello, UDP!", help="Message to send")
    parser.add_argument("-b", "--broadcast", nargs='+', metavar='IFACE', help="Broadcast on these interface names (space-separated)")
    args = parser.parse_args()

    # Validate arguments
    if args.dest_port and not (args.target_ip or args.broadcast):
        parser.error("--dest-port requires --target-ip or --broadcast")
    if not args.dest_port and not args.recv_port:
        parser.error("At least one of --dest-port or --recv-port must be specified")

    stop_event = threading.Event()
    threads = []

    # Start receiver thread if recv_port is specified
    if args.recv_port:
        receiver_thread = threading.Thread(target=udp_receiver, args=(args.recv_port, stop_event))
        receiver_thread.start()
        threads.append(receiver_thread)

    # Start sender thread if dest_port is specified
    if args.dest_port:
        sender_thread = threading.Thread(
            target=udp_sender,
            args=(args.target_ip, args.dest_port, args.period, args.message, stop_event, bool(args.broadcast), args.broadcast)
        )
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
