from Crypto.Cipher import AES
from Crypto.Util import Counter
from Crypto.Random import get_random_bytes
import os
import base64

# Shared secret key (32 bytes = 256-bit key)
SECRET_KEY = b'ThisIsAStaticKeyForTesting123456'

def encrypt_message(message: str) -> str:
    iv = get_random_bytes(16)  # 128-bit IV
    ctr = Counter.new(128, initial_value=int.from_bytes(iv, byteorder='big')) # new ctr each time as per AES CTR mode 
    cipher = AES.new(SECRET_KEY, AES.MODE_CTR, counter=ctr)
    ciphertext = cipher.encrypt(message.encode('utf-8'))
    encrypted_data = iv + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8') # message is a string

def decrypt_message(data: str) -> str:
    # Ensure correct padding
    missing_padding = len(data) % 4
    if missing_padding != 0:
        data += '=' * (4 - missing_padding)
    
    raw_data = base64.b64decode(data.encode('utf-8'))
    iv = raw_data[:16]
    ciphertext = raw_data[16:]
    ctr = Counter.new(128, initial_value=int.from_bytes(iv, byteorder='big'))
    cipher = AES.new(SECRET_KEY, AES.MODE_CTR, counter=ctr)
    plaintext = cipher.decrypt(ciphertext).decode('utf-8')
    return plaintext
