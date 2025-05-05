"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.

TODO: Fix the message synchronization issue using concurrency (Tier 1, item 1).
"""

import socket
import threading
import os
import uuid

HOST = '127.0.0.1'
PORT = 5000

CLIENT_ID_DIR = "client_ids"
os.makedirs(CLIENT_ID_DIR, exist_ok=True)  # Ensure the directory exists
CLIENT_ID_FILE = os.path.join(CLIENT_ID_DIR, f"client_id_{os.getpid()}.txt")  # Unique per process


def get_or_create_client_id():
    if os.path.exists(CLIENT_ID_FILE):
        with open(CLIENT_ID_FILE, 'r') as f:
            client_id = f.read().strip()
            if client_id:
                print(f"[INFO] Reusing client ID: {client_id}")
                return client_id
    return None

def receive_messages(rfile, socket_obj, stop_event):
    try:
        while not stop_event.is_set():
            line = rfile.readline()
            if not line:
                print("[INFO] Server disconnected.")
                stop_event.set()
                break

            line = line.strip()

            if line == "GRID":
                # Begin reading board lines
                print("\n[Board]")
                while True:
                    board_line = rfile.readline()
                    if not board_line or board_line.strip() == "":
                        break
                    print(board_line.strip())
            else:
                # Normal message
                print(line)

    except Exception as e:
        print(f"[ERROR] An error occurred in the receive thread: {e}")

    finally:
        socket_obj.close()

def handle_user_input(wfile, stop_event):
    try:
        while not stop_event.is_set():
            user_input = input(">> ")
            if stop_event.is_set():  # Exit if the server disconnects
                break
            wfile.write(user_input + '\n')
            wfile.flush()
    except Exception as e:
        print(f"[ERROR] An error occurred in the input thread: {e}")

def main():
    stop_event = threading.Event()  # Create a stop event to coordinate threads
    stored_client_id = get_or_create_client_id()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')

        wfile.write((stored_client_id or "") + "\n")
        wfile.flush()

        confirmed_id = rfile.readline().strip()

        if not stored_client_id or confirmed_id != stored_client_id:
            with open(CLIENT_ID_FILE, 'w') as f:
                f.write(confirmed_id)
            print(f"[INFO] New client ID assigned: {confirmed_id}")

        threading.Thread(target=receive_messages, args=(rfile, s, stop_event), daemon=True).start()

        threading.Thread(target=handle_user_input, args=(wfile, stop_event), daemon=True).start()

        stop_event.wait()
        print("[INFO] Exiting...")

if __name__ == "__main__":
    main()
