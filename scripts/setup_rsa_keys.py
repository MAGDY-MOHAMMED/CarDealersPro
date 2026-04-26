import sys
from pathlib import Path
# Add parent directory to path to allow imports
root_path = Path(__file__).parent.parent
sys.path.append(str(root_path))
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from core.logging_config import logger



def generate_rsa_key():
    root_path = Path(__file__).parent.parent # get the parent directory of the current file , __file__ means the current file path
    private_key_path = root_path / "private.pem" # create the path for the private key
    public_key_path = root_path / "public.pem" # create the path for the public key
    logger.info("Generating RSA keys...", extra={"request_id": None})

    private_key_obj = rsa.generate_private_key(
        public_exponent=65537, # standard public exponent
        key_size=2048, # key size in bits
    )
    
    # Serialize private key how ? it's a method of the private key object
    private_pem = private_key_obj.private_bytes(
        encoding=serialization.Encoding.PEM, # PEM format
        format=serialization.PrivateFormat.PKCS8, # PKCS8 format means ? it's a standard format for storing private keys
        encryption_algorithm=serialization.NoEncryption() # no encryption
    )
    private_key_path.write_bytes(private_pem)
    logger.info(f"Private key saved to {private_key_path}", extra={"request_id": None})
    
    # Serialize public key how ? it's a method of the private key object
    public_pem = private_key_obj.public_key().public_bytes( # get the public key from the private key object how ? it's a property of the private key object how 
        encoding=serialization.Encoding.PEM, # PEM format
        format=serialization.PublicFormat.SubjectPublicKeyInfo # SubjectPublicKeyInfo format
    )
    public_key_path.write_bytes(public_pem)
    logger.info(f"Public key saved to {public_key_path}", extra={"request_id": None})


if __name__ == "__main__":
    generate_rsa_key()
    
    