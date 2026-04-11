import bcrypt
from core.logging_config import logger


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8') # encode the password to bytes why ? because bcrypt.hashpw() expects bytes
    salt = bcrypt.gensalt() # generate a random salt , salt means random data that is added to the password before hashing to make it more secure
    hashed_password = bcrypt.hashpw(pwd_bytes, salt) # hash the password
    return hashed_password.decode('utf-8') # return the hashed password as a string , decode means converting bytes to string
    
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),  # encode the plain password to bytes why ? because bcrypt.checkpw() expects bytes
        hashed_password.encode('utf-8')  # encode the hashed password to bytes why ? because bcrypt.checkpw() expects bytes
    ) # verify the password
