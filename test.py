from crypto_utils import encrypt_message, decrypt_message

# Example Usage

message = "Hello, this is a secret message!"
print("Original Message:", message)

# Encrypt the message
encrypted_message = encrypt_message(message)
print("Encrypted Message:", encrypted_message)

# Decrypt the message
decrypted_message = decrypt_message(encrypted_message)
print("Decrypted Message:", decrypted_message)
