from crypto_utils import encrypt_message, decrypt_message
import zlib

# Example Usage

message = "Hello, this is a secret message!"
print("Original Message:", message)

# Encrypt the message
encrypted_message = encrypt_message(message)
print("Encrypted Message:", encrypted_message)

# Decrypt the message
decrypted_message = decrypt_message(encrypted_message)
print("Decrypted Message:", decrypted_message)


def generate_crc32_checksum(data):
    return zlib.crc32(data) & 0xFFFFFFFF

def verify_checksum(message, expected_checksum):
    message_data, checksum_str = message.rsplit('|', 1) # message = data|checksum
    checksum = int(checksum_str)
    computed_checksum = generate_crc32_checksum(message_data.encode()) # generate checksum from message and compare with the received checksum
    return checksum == computed_checksum

def send(user_input):
    """formerly handle_user_input"""
    try:
        # while not stop_event.is_set():
        #     user_input = input(">> ")
        #     if stop_event.is_set():  # Exit if the server disconnects
        #         break
            
        # encrypt the user input before adding the checksum
        encrypted_message = encrypt_message(user_input) # this is in bytes
        
        checksum = generate_crc32_checksum(encrypted_message.encode())
        message = f"{encrypted_message}|{checksum}"

        msg = message + "\n" # writes the (iv + msg)|checksum packet to the wfile
        return msg
        # wfile.flush()
    except Exception as e:
        print(f"[ERROR] An error occurred in the input thread: {e}")

    
def recv_with_checksum(message_with_checksum):
    """
    Receive a message with checksum from the client and verify its integrity.
    
    At this point the message looks like
    (iv + cyphertext)|checksum
    """
    try:
        message, received_checksum = message_with_checksum.rsplit('|', 1) 
        calculated_checksum = zlib.crc32(message.encode())  
        
        if int(received_checksum) == calculated_checksum: 
            return recv_encrypted_data(message)
    except:
        pass  # Silently discard any malformed or invalid messages
    return None

def recv_encrypted_data(enc_message):
    """
    At this point, the message looks like
    iv + cyphertext
    
    we know the iv is 16 bytes long
    """
    plaintext = decrypt_message(enc_message)
    return plaintext

input = "olivia"
encrypted = send(input)
print("Encrypted message")
print(encrypted)

decrypted = recv_with_checksum(encrypted)
print("Decrypted")
print(decrypted)
