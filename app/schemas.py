from pydantic import BaseModel, ConfigDict , EmailStr, Field
from uuid import UUID
from pydantic_partial import create_partial_model
from datetime import datetime
from typing import Optional
from app.models import UserRole, MediaType, LoanStatus, PaymentMethod

class CarsBase(BaseModel):
    brand : str
    model : str
    year : int
    price_consumer : float
    price_dealer : Optional[float] = None
    color : str | None = None

# i will use RS256 algorithm and .pem file to store the public key and private key and to be ordered

class CarCreate(CarsBase): # this model is used to create a car
    pass  

class CarResponse(CarsBase): # when pydantic validates the data, it will convert the UUID object to a string
    id : UUID
    owner_id : UUID | None = None
    owner_name: str | None = None
    ratings_count : int = 0
    average_rating: float | None
    created_at : datetime
    model_config = ConfigDict(from_attributes=True) # عشان يتعامل مع DB Objects as a dictionary , from_attributes means it will convert the DB Object to a dictionary
# i want to use UUID in the response to identify the car

class UserBase(BaseModel):
    email : EmailStr
    full_name : str 
    role: UserRole = UserRole.CLIENT 


class UserCreate(UserBase): # we don't want to expose the password in the response
    password : str



class UserResponse(UserBase):
    id : UUID
    created_at : datetime
    model_config = ConfigDict(from_attributes=True)
# i want to use UUID in the response to identify the user

class UserLogin(BaseModel):
    email : EmailStr
    password : str # we need to authenticate the user


class Token(BaseModel): # why not UserBase? 
    access_token : str # we need to specify the access token
    token_type : str # we need to specify the type of the token


class TokenData(BaseModel):
    user_id : UUID | None = None
    role : str | None = None


class RatingBase(BaseModel):
    value_score: int = Field(..., ge=0, le=100)
    comment: Optional[str] = None
    ai_confidence: Optional[float] = None



CarUpdate = create_partial_model(CarsBase) # this will create a model that has all the fields of CarsBase but all of them are optional


class TransferOwnershipRequest(BaseModel):
    new_owner_id: UUID


class CarMediaBase(BaseModel):
    media_url: str
    media_type: MediaType = MediaType.IMAGE
    file_size: int


class CarMediaCreate(CarMediaBase):
    car_id: UUID


class CarMediaResponse(CarMediaBase):
    id: UUID
    car_id: UUID
    car_name: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Finance Schemas (MAMAA Grade - DB-level implementation)
class LoanApplicationCreate(BaseModel):
    client_id: UUID
    car_id: UUID
    bank_id: UUID
    down_payment: float = Field(..., gt=0, description="Down payment amount") # gt means greater than
    tenure_months: int = Field(..., gt=0, le=84, description="Loan term in months (max 7 years)") # le means less than or equal

    model_config = ConfigDict(from_attributes=True)


class LoanApplicationResponse(BaseModel):
    id: UUID
    client_id: UUID
    car_id: UUID
    bank_id: UUID | None
    loan_amount: float
    down_payment: float
    tenure_months: int
    interest_rate: float
    monthly_installment: float
    status: LoanStatus
    applied_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoanApplicationUpdate(BaseModel):
    status: LoanStatus | None = None
    interest_rate: float | None = Field(None, ge=0, le=30, description="Interest rate percentage")

    model_config = ConfigDict(from_attributes=True)


class LoanDisbursementCreate(BaseModel):
    application_id: UUID
    amount: float = Field(..., gt=0, description="Disbursement amount")
    bank_reference: str = Field(..., min_length=1, description="Bank reference number")
    notes: str | None = Field(None, description="Optional notes")

    model_config = ConfigDict(from_attributes=True)


class LoanDisbursementResponse(BaseModel):
    id: UUID
    application_id: UUID
    amount: float
    bank_reference: str
    disbursement_date: datetime
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class LoanRepaymentCreate(BaseModel):
    application_id: UUID
    amount: float = Field(..., gt=0, description="Repayment amount")
    payment_method: str = Field(default="E-Wallet", description="Payment method")
    reference: str | None = Field(None, description="Payment reference")

    model_config = ConfigDict(from_attributes=True)


class LoanRepaymentResponse(BaseModel):
    id: UUID
    application_id: UUID
    amount: float
    payment_method: str
    payment_date: datetime
    reference: str | None

    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    buyer_id: UUID
    seller_id: UUID
    car_id: UUID
    amount: float = Field(..., gt=0, description="Transaction amount")
    method: PaymentMethod = Field(default=PaymentMethod.CASH, description="Payment method")
    reference: str | None = Field(None, description="Transaction reference")

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    id: UUID
    buyer_id: UUID
    seller_id: UUID
    car_id: UUID
    amount: float
    method: PaymentMethod
    reference: str | None
    transaction_date: datetime

    model_config = ConfigDict(from_attributes=True)


class FinanceCalculatorRequest(BaseModel):
    principal: float = Field(..., gt=0, description="Loan principal amount")
    annual_interest_rate: float = Field(..., ge=0, le=30, description="Annual interest rate percentage")
    months: int = Field(..., gt=0, le=84, description="Loan term in months")

    model_config = ConfigDict(from_attributes=True)


class FinanceCalculatorResponse(BaseModel):
    monthly_payment: float
    total_payment: float
    total_interest: float

    model_config = ConfigDict(from_attributes=True)


# Repayment Schedule Schemas (MAMAA Grade - DB-level implementation)
class RepaymentScheduleResponse(BaseModel):
    id: UUID
    application_id: UUID
    installment_number: int
    due_date: datetime
    amount: float
    principal_amount: float
    interest_amount: float
    remaining_balance: float
    is_paid: bool
    paid_date: Optional[datetime] = None
    paid_amount: Optional[float] = None
    overdue_days: int = 0

    model_config = ConfigDict(from_attributes=True)


class RepaymentScheduleSummary(BaseModel):
    application_id: UUID
    total_installments: int
    paid_installments: int
    remaining_installments: int
    total_amount: float
    paid_amount: float
    remaining_amount: float
    next_payment_date: Optional[datetime] = None
    next_payment_amount: Optional[float] = None
    overdue_amount: float = 0

    model_config = ConfigDict(from_attributes=True)

class PaymentSummaryResponse(BaseModel):
    application_id: UUID # Application ID
    amount_received: float # Total amount received from customer
    amount_applied: float # Amount applied to outstanding balance
    remaining_unpaid: float # Remaining unpaid amount after payment
    installments_updated: int # Number of installments updated

    model_config = ConfigDict(from_attributes=True)


class PricePredictRequest(BaseModel):
    brand: str
    model: str
    year: int
    mileage: Optional[float] = None
    condition: str = "used"

class PricePredictResponse(BaseModel):
    predicted_price: float
    confidence: float

class ImageInspectResponse(BaseModel):
    damage_percentage: float
    issues: list[str] = []