"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.
"""
import socket
import threading
import zlib 
from crypto_utils import decrypt_message, encrypt_message

HOST = '127.0.0.1'
PORT = 5000

def generate_crc32_checksum(data):
    return zlib.crc32(data) & 0xFFFFFFFF

def verify_checksum(message, expected_checksum):
    message_data, checksum_str = message.rsplit('|', 1) # message = data|checksum
    checksum = int(checksum_str)
    computed_checksum = generate_crc32_checksum(message_data.encode()) # generate checksum from message and compare with the received checksum
    return checksum == computed_checksum


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
                if '|' in line:
                    seq, message_enc, _ = line.rsplit('|', 2)  # discard checksum
                    # message shoudl be encrypted and therefore in the format (iv+ciphertext)
                    message = decrypt_message(message_enc)
                    print(message)
                else:
                    print(line)

    except Exception as e:
        print(f"[ERROR] An error occurred in the receive thread: {e}")

    finally:
        socket_obj.close()


def handle_user_input(wfile, stop_event):
    seq_num = 0
    try:
        while not stop_event.is_set():
            user_input = input(">> ")
            if stop_event.is_set():  # Exit if the server disconnects
                break
            
            # encrypt the user input before adding the checksum
            encrypted_message = encrypt_message(user_input) # this is in bytes
            message_with_seq = f"{seq_num}|{encrypted_message}"
            
            checksum = generate_crc32_checksum(message_with_seq.encode())
            message = f"{message_with_seq}|{checksum}"

            wfile.write(message + "\n") # writes the (iv + msg)|checksum packet to the wfile
            wfile.flush()
            
            seq_num +=1 
    except Exception as e:
        print(f"[ERROR] An error occurred in the input thread: {e}")


def main():
    stop_event = threading.Event()  # Create a stop event to coordinate threads

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')

        threading.Thread(target=receive_messages, args=(rfile, s, stop_event), daemon=True).start()

        threading.Thread(target=handle_user_input, args=(wfile, stop_event), daemon=True).start()

        stop_event.wait()

        print("[INFO] Exiting...")

if __name__ == "__main__":
    main()
