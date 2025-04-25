"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.

TODO: Fix the message synchronization issue using concurrency (Tier 1, item 1).
"""

import socket
import threading

HOST = '127.0.0.1'
PORT = 5000

def receive_messages(rfile):
    try:
        while True:
            line = rfile.readline()
            if not line:
                print("[INFO] Server disconnected.")
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


'''
TODO:: close socked when you exit the game by quiting the game 
''' 
def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')

        threading.Thread(target=receive_messages, args=(rfile,), daemon=True).start()

        try:
            while True:
                user_input = input(">> ")
                wfile.write(user_input + '\n')
                wfile.flush()

        except KeyboardInterrupt:
            print("\n[INFO] Exiting...")

        finally:
            s.close()

if __name__ == "__main__":
    main()
