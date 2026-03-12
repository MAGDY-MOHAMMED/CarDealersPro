import re
from typing import Optional,Any


class DataValidator :
    @staticmethod
    def validate_email (email : str) -> bool : 
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool (re.match(pattern,email)) 
    @staticmethod
    def validate_tax_id (tax_id : str) -> bool : 
        pattern = r'^[0-9]{11}$'
        return bool (re.match(pattern,tax_id)) 
    @staticmethod
    def validate_swift (swift : str) -> bool : 
        pattern = r'^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$'
        return bool (re.match(pattern,swift)) 
    @staticmethod
    def normalize_string (value : Any) -> str : # normalize the string
        if not value : return ""
        return str(value).strip().lower()
