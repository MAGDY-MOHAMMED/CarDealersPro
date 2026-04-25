import re
from typing import Optional,Any


class DataValidator :
    @staticmethod
    def validate_email (email : str) -> bool : 
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool (re.match(pattern,email)) 
    @staticmethod
    def validate_tax_id (tax_id : str) -> bool : 
        if not isinstance(tax_id, str):
            return False
        return len(tax_id) <= 20
    @staticmethod
    def validate_swift (swift : str) -> bool : 
        if not isinstance(swift, str):
            return False
        return len(swift) <= 11
    @staticmethod
    def normalize_string (value : Any) -> str : # normalize the string
        if isinstance(value, str):
            return value.strip().lower()
        return str(value)
    @staticmethod
    def validate_currency(code: str) -> bool:
        return code in ['USD', 'EUR', 'GBP', 'JPY', 'CAD']

    @staticmethod
    def validate_phone(phone: str) -> bool:
        if not isinstance(phone, str):
            return False
        clean_phone = re.sub(r'\D', '', phone)     # Remove non-digit characters , re.sub means replace
        return 10 <= len(clean_phone) <= 15

    @staticmethod
    def validate_url(url: str) -> bool:
        if not isinstance(url, str):
            return False
        pattern = r'https?://(?:www\.)?[-\w.]{2,20}[-\w.]*'        # Basic URL pattern check
        return bool(re.search(pattern, url))
