import re
from typing import Dict,Any, Optional,List
from enum import Enum
from dataclasses import dataclass,field
from datetime import datetime
import uuid
from enum import unique
from dataclasses import fields
from core.validator import DataValidator
from core.config import VEHICLE_CATEGORIES, LOAN_TYPES, SUPPORTED_CURRENCIES, INSPECTOR_SPECIALIZATIONS
from core.base import BaseSchema , StorageMixin


DEFAULT_VEHICLE_CATEGORIES = ["car", "motorcycle", "truck", "van", "bus", "suv", "pickup"]
DEFAULT_LOAN_TYPES = ["New Car", "Used Car", "Refinance"]
DEFAULT_CURRENCIES = ["EGP", "USD", "EUR", "GBP"]
DEFAULT_INSPECTOR_SPECIALS = ["Mechanic", "Body", "Electrical", "Interior", "Suspension Mechanic "]


@unique
class UserRole (Enum) :
    CLIENT= "CLIENT"
    DEALER= "DEALER"
    BANK= "BANK"
    INSURANCE= "INSURANCE"
    INSPECTOR= "INSPECTOR"
    ADMIN= "ADMIN"
    @classmethod
    def list_roles(cls)  -> List[str] : # for api if they need the list of rules 
        return [role.value for role in cls]
    def __str__(self) -> str : 
        return self.value
    @classmethod    
    def is_valid(cls,role_name:str)  -> bool : 
        return role_name in cls.list_roles()
@unique 
class UserStatus (Enum) : 
    PENDING = "PENDING"        
    ACTIVE = "ACTIVE"          
    SUSPENDED = "SUSPENDED"    
    BANNED = "BANNED"
@dataclass
class BaseUserSchema (BaseSchema) :
    role : UserRole = UserRole.CLIENT
    email : str = ""
    phone : str = ""
    full_name : str = ""
    status : UserStatus = UserStatus.PENDING
    is_verified : bool = False
    def is_active (self) -> bool :
        return self.status== UserStatus.ACTIVE
    def __post_init__ (self) :
        super().__post_init__()        


@dataclass
class ClientProfile (BaseUserSchema) :     #inheritance
    monthly_income : float = 0.0
    employer : Optional [str] = None
    has_tax_card : bool = False
    current_liabilities : float = 0.0
    credit_score : Optional [int] = None
    job_title : Optional [str] = None
    @classmethod
    def create_guest (cls,email:str ,name : str) :
        return cls (
            role=UserRole.CLIENT, 
            email=email, 
            phone = "N/A", # not available for guest ضحكنا عالكلاس باي حاجه عشان فوق الزامي يبقي في رقم واحنا عايزين نطبع ب اسم 
            full_name=name, 
            monthly_income = 0.0 
        )

    
@dataclass
class DealerProfile (BaseUserSchema):
    company_name : str = ""
    tax_id : Optional [str] = None
    commercial_register : Optional [str] = None
    subscription_plan : str= "FREE"
    allowed_categories : List [str] = field (default_factory=lambda : list(DEFAULT_VEHICLE_CATEGORIES)) #  more  later  # we need to make it a list not a same string 
    inventory_count : int = 0 #we need in vehicles to count the number of vehicles in the inventory
    @classmethod
    def register_new_dealer (cls, email : str, company_name :str , full_name: str , tax_id: Optional[str] = None) -> "DealerProfile" : 
        if not DataValidator.validate_email(email):
            raise ValueError(f"Invalid email address: {email}")
        if tax_id and not DataValidator.validate_tax_id(tax_id):
            raise ValueError(f"Invalid tax ID: {tax_id}")
        
        return cls (
            role=UserRole.DEALER,
            email=email.lower(),
            company_name=company_name,
            full_name=full_name,
            phone="N/A",
            tax_id=tax_id
        )
@dataclass        
class BankProfile (BaseUserSchema):
    bank_name: str = "" # أضفنا قيمة افتراضية
    swift_code: str = "" # أضفنا قيمة افتراضية
    annual_interest_rate: float = 10.0
    rates: Dict[str, float] = field(default_factory=lambda: {
        "new": 10.0, # فائدة سنوية للسيارات الجديدة
        "used": 14.0 # فائدة سنوية للسيارات المستعملة
    })
    min_dp_percent: Dict[str, float] = field(default_factory=lambda: {
        "new": 10.0, # حد أدنى للمقدم للسيارات الجديدة
        "used": 25.0 # حد أدنى للمقدم للسيارات المستعملة
    })
    max_months: Dict[str, int] = field(default_factory=lambda: {
        "new": 84,  # 7 سنين
        "used": 60  # 5 سنين
    })
    iban : Optional [str] = None
    min_down_payment : float = 0.0
    max_loan_amount : float =1000000.0
    supported_loan_types : List [str] = field (default_factory=lambda : LOAN_TYPES)      
    supported_currencies : list [str] = field (default_factory=lambda : SUPPORTED_CURRENCIES)
    @classmethod
    def register_new_bank (cls, email : str, bank_name :str , swift_code : str , iban : Optional [str] = None )      -> "BankProfile" : 
        if not DataValidator.validate_swift(swift_code):
            raise ValueError(f"Invalid SWIFT/BIC Code: {swift_code}. Must be 8 or 11 characters.")
        if not DataValidator.validate_email(email):
            raise ValueError(f"Invalid email address: {email}")

        bank = cls (
            role=UserRole.BANK,
            email=email.lower(),
            bank_name=bank_name,
            swift_code=swift_code.upper(),
            iban=iban,
            phone="N/A"
        )
        bank.annual_interest_rate = bank.rates["new"] 
        return bank
@dataclass
class InspectorProfile (BaseUserSchema) : 
    specialization : List [str] = field (default_factory=lambda : INSPECTOR_SPECIALIZATIONS )
    years_of_experience : int = 0
    trust_score: float = 5.0 
    total_inspection_count : int = 0
    is_new : bool = True
    is_available : bool = True
    account_status : str = "PENDING_APPROVAL"
    @classmethod
    def register_new_inspector (cls,email:str,full_name:str   )-> "InspectorProfile" : 
        return cls (
            role=UserRole.INSPECTOR,
            email=email.lower(),
            full_name=full_name,
            phone="N/A"
        )
@dataclass
class AdminProfile (BaseUserSchema):
    @classmethod
    def register_new_admin (cls,email:str,full_name:str   )-> "AdminProfile" : 
        return cls (
            role=UserRole.ADMIN,
            email=email.lower(),
            full_name=full_name,
            phone="N/A"
        )
class IdentityManager (StorageMixin[BaseUserSchema]): # the store of data  # the email is the key in the dict
    def __init__(self) : 
        super().__init__(BaseUserSchema, "users.json")        
    def register_user (self, user : BaseUserSchema) -> "BaseUserSchema" : 
        self.data[user.email.lower()] = user # بنستخدم self.data اللي في المكس-إن  # that means we are using the data from the StorageMixin
        self.save() 
        return user

    def get_by_email (self, email : str) -> Optional [BaseUserSchema] : 
        return self.data.get(email.lower())  # get means if none it will return none without crash 
    def find_users (self,**kwargs) -> List [BaseUserSchema] : # find users by any key value pair donot forget ** 
        return self.find_by(**kwargs)

    def update_user (self, email :str ,updated_user : BaseUserSchema ) -> "BaseUserSchema" : 
        email_key = email.lower()
        if email_key not in self.data : 
            raise ValueError(f" User with {email} not found ")
        new_email_key= updated_user.email.lower()
        if new_email_key != email_key and new_email_key in self.data : # if the email is not the same and the new email is already in the users
            raise ValueError(f" User with email {new_email_key} already exists ") 
        self.data.pop(email_key) # remove the old user pop return the object if you need it !
        self.data[new_email_key] = updated_user # add the new user
        self.save()
        print(f"User {updated_user.email} updated successfully")
        return updated_user


@dataclass
class UserManager : # print the rules # the manager that apply the rules 
    def __init__(self, identity_manager: IdentityManager):
        self.identity_manager = identity_manager
    def update_user(self, email: str, updated_user: BaseUserSchema) -> BaseUserSchema:
        current_user = self.identity_manager.get_by_email(email)
        if not current_user:
            raise ValueError(f"User {email} not found")
            
        if current_user.status == UserStatus.BANNED:
            raise PermissionError("Action denied: User is banned")
        if not DataValidator.validate_email(updated_user.email):
            raise ValueError("Invalid email format")
        updated_user.sync_data()
        return self.identity_manager.update_user(email, updated_user)











    




        



    

    
