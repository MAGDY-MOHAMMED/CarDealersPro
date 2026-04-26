from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum, unique
from datetime import datetime
from core.base import BaseSchema , StorageMixin
from core.auth import ClientProfile, BankProfile , User
from core.vehicles import VEHICLE , InventoryManager
from core.config import FINANCE_CONFIG
import os
import json


@unique
class LoanStatus (Enum) :
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    DISBURSED = "DISBURSED" # تم صرف المبلغ
    REPAYING = "REPAYING"   # قيد السداد
    PAID_OFF = "PAID_OFF"     # مسدد بالكامل

@unique
class PaymentMethod(Enum):
    CASH = "CASH"
    FINANCE = "FINANCE"
    B2B_TRANSFER = "B2B_TRANSFER" # تاجر بيشتري من تاجر

@dataclass
class Transaction(BaseSchema):
    buyer_id: str = ""
    seller_id: str = ""
    vehicle_vin: str = ""
    amount: float = 0.0
    method: PaymentMethod = PaymentMethod.CASH
    reference: str = "" # رقم الشيك أو إيصال الإيداع

class FinanceCalculator :
    @staticmethod
    def calculate_monthly_payment(principal : float ,annual_interest_rate : float , months : int ) -> float :
        if months <= 0 or annual_interest_rate <= 0: return round(principal / (months or 1), 2)  # round means to round the number to 2 decimal places
        monthly_rate = (annual_interest_rate/100)/12 
        payment = (principal * monthly_rate) / (1 - (1 + monthly_rate)** -months ) # EMI Formula 
        return round(payment, 2)

@dataclass
class LoanApplication (BaseSchema):
    client_id : str = ""
    vehicle_vin : str = ""
    bank_id : str = ""
    loan_amount: float = 0.0
    down_payment : float = 0.0
    tenure_months : int = 0 # number of months
    interest_rate : float =0.0 # it will calculated when the req is calculated 
    monthly_installment : float = 0.0
    status : LoanStatus = LoanStatus.PENDING 
    applied_at : datetime = field(default_factory=datetime.now)

    def __post_init__(self):
         super().__post_init__()
         if self.loan_amount > 0 and self.monthly_installment == 0:
            principal = self.loan_amount - self.down_payment
            self.monthly_installment = FinanceCalculator.calculate_monthly_payment(
                self.loan_amount, self.interest_rate, self.tenure_months
            ) # calculate monthly installment when created the request if not calculated 

@dataclass
class LoanDisbursement (BaseSchema) :
    application_id :str = ""
    amount : float = 0.0
    bank_reference : str = ""
    disbursement_date: datetime = field(default_factory=datetime.now)
    notes: str = "Funds transferred to dealer account." 
    def __post_init__(self):
        super().__post_init__()
        if self.amount <= 0: # Critical validation
            raise ValueError("[Critical] Disbursement amount must be positive.")
        if not self.application_id: # Critical validation
            raise ValueError("[Critical] Application ID is mandatory for disbursement.")
        

@dataclass
class LoanRepayment (BaseSchema) :
    application_id :str = ""
    amount : float = 0.0
    payment_method : str = "E-Wallet"

class FinanceManager :
    def __init__(self) :
        self.apps_store = StorageMixin(LoanApplication, "loan_apps.json")
        self.disburse_store = StorageMixin(LoanDisbursement, "disbursements.json")
        self.repay_store = StorageMixin(LoanRepayment, "repayments.json")
        self.transactions_store = StorageMixin(Transaction, "transactions.json")

    def process_cash_sale (self, buyer: Any, vehicle: VEHICLE, inventory_manager, ref: str = "") :
        txn = Transaction(
            buyer_id=buyer.email, 
            seller_id=vehicle.owner_id, #the dealer who show the car 
            vehicle_vin=vehicle.vin,
            amount=vehicle.price,
            method=PaymentMethod.CASH,
            reference=ref
        )
    
        self.transactions_store.data[txn.uid] = txn
        self.transactions_store.save()
        inventory_manager.transfer_ownership(vehicle.vin, buyer.email)
        vehicle.status = "SOLD"
        inventory_manager.save_to_disk() # save the inventory to disk
        print(f"[Cash Sale] Vehicle {vehicle.vin} sold to {buyer.email}")
        return txn
    def complete_finance_sale (self ,app_id : str, inventory_manager , bank_ref: str ) :
        app = self.apps_store.get_by_id (app_id)
        if not app:
            raise KeyError(f"Application {app_id} not found.")
        self.record_disbursement(app_id,bank_ref, inventory_manager)
        inventory_manager.transfer_ownership(app.vehicle_vin, app.client_id)

        txn = Transaction (
            buyer_id = app.client_id,
            seller_id= inventory_manager.get_vehicle_by_vin(app.vehicle_vin).owner_id, # the dealer who sold the car
            vehicle_vin=app.vehicle_vin,
            amount=app.loan_amount + app.down_payment,
            method=PaymentMethod.FINANCE,
            reference=bank_ref # 
        )
        self.transactions_store.data[txn.uid] = txn # save the transaction
        self.transactions_store.save() # save to disk
        return txn
    def create_application (self ,**kwargs) -> LoanApplication :
        app = LoanApplication (**kwargs)
        self.apps_store.data[app.uid] = app
        self.apps_store.save()
        return app
    
    def record_repayment(self, app_id: str, amount: float): # ssave the installment
        repayment = LoanRepayment(application_id=app_id, amount=amount)
        self.repay_store.data[repayment.uid] = repayment # save the installment
        self.repay_store.save() # save to disk
        return repayment
    def get_client_history (self, client_id :str )-> List [LoanApplication] :
        return self.apps_store.find_by (client_id=client_id)
    def get_overdue_reports (self) :
     #   """(Future Placeholder for AI Integration)"""
        pass

    def calculate_custom_interest(self, vehicle, client, down_payment):

        base_rate = FINANCE_CONFIG["default_interest_rates"][vehicle.condition.lower()]
        
        dp_percent = (down_payment / vehicle.price) * 100
        if dp_percent > 40:
            base_rate -= 1.0
            
        return base_rate

    def apply_for_loan (self ,client: ClientProfile ,vehicle : VEHICLE ,bank : BankProfile , down_payment: float, months: int ) -> LoanApplication :
        car_condition = vehicle.condition.lower() # new or used
        if car_condition not in ["new", "used"]:
            raise ValueError("Car condition must be 'new' or 'used'")
        interest_rate = bank.rates.get(car_condition, FINANCE_CONFIG["default_interest_rates"].get(car_condition, 12.0)) # get the interest rate from the car condition

        dp_percent = (down_payment / vehicle.price) * 100
        if dp_percent > 40: #
            interest_rate -= 1.0 #
        min_dp_req = bank.min_dp_percent.get(car_condition, FINANCE_CONFIG["default_min_down_payment"].get(car_condition, 15.0)) # if itis not in the bank get it from FINANCE_CONFIG [condition]
        required_dp = vehicle.price * (min_dp_req / 100) #calculate the actual minimum down payment
        if down_payment < required_dp:
            raise ValueError(f"Down payment too low. Bank/System requires {min_dp_req}% ({required_dp} EGP) for {car_condition} cars.") #
        max_months_req = bank.max_months.get(car_condition, FINANCE_CONFIG["max_tenure_months"].get(car_condition, 60)) #if the car condition is not in the bank get it from FINANCE_CONFIG
        if months > max_months_req : #if the months is more than the max months required by the bank
            raise ValueError(f"Loan term too long! Maximum for {car_condition} cars is {max_months_req} months")        
        loan_amount = vehicle.price - down_payment
        installment = FinanceCalculator.calculate_monthly_payment(loan_amount, interest_rate, months)
        income_limit = client.monthly_income * FINANCE_CONFIG.get("income_debt_ratio", 0.40) #
        if installment > income_limit : 
            print(f"⚠️ Loan Rejected: Installment {installment:.2f} exceeds 40% of income ({max_allowed_installment:.2f})")
            return None
        if vehicle.is_inspected and hasattr(vehicle, 'inspection_report_id'): # validate the inspection 
        # دي هنكملها لما نخلص موديول الفحص عشان نسحب الـ Score
            pass
        app = LoanApplication(
            client_id=client.uid, # client unique id
            vehicle_vin=vehicle.vin, # vehicle unique id
            bank_id=bank.uid, # bank unique id
            loan_amount=loan_amount,
            down_payment=down_payment,
            tenure_months=months,
            interest_rate=interest_rate,
            monthly_installment = installment,
            status=LoanStatus.PENDING
        )
        self.apps_store.data[app.uid] = app # add the application to the dict apllications
        self.apps_store.save() # save the data to the file
        self.apps_store.refresh() # refresh the data
        app = self.apps_store.get_by_id(app.uid) # get the application by id
        if not app: #
            raise IOError(f"Critical: Failed to persist Application {app.uid} to disk.") 
        print(f"💰 Loan Application Created: {app.uid} | Interest: {interest_rate}%")
        return app
    def record_disbursement (self ,app_id : str ,bank_ref: str, inventory_manager) -> LoanDisbursement :
        app = self.apps_store.get_by_id (app_id)
        if not app :
            raise KeyError(f"Application {app_id} not found.")
        
        if app.status != LoanStatus.APPROVED: # check if the application is approved
            raise PermissionError(f"Cannot disburse funds for status: {app.status}")
        disbursement = LoanDisbursement (
            application_id=app_id,
            amount=app.loan_amount,
            bank_reference=bank_ref
        )
        # update the loan 
        app.status = LoanStatus.DISBURSED
        app.updated_at = datetime.now()
        self.apps_store.save()

        vehicle = inventory_manager.get_vehicle_by_vin(app.vehicle_vin) # Update vehicle status to DISBURSED
        if vehicle:
            vehicle.status = "DISBURSED"
            inventory_manager.save_to_disk()
        print(f"[Success] Disbursement {disbursement.uid} processed for App {app_id}")
        self.disburse_store.data[disbursement.uid] = disbursement # add the disbursement to the dict disbursements
        self.disburse_store.save() # save the disbursement to the file
        return disbursement
    def record_repayment (self, app_id : str , amount : float) :
        repayment = LoanRepayment(application_id=app_id, amount=amount)
        self.repay_store.data[repayment.uid] = repayment
        self.repay_store.save()
        return repayment
    def query_applications (self, **filters ) :
        return self.apps_store.find_by (**filters) 
    def query_repayments(self, **filters):
        return self.repay_store.find_by(**filters)

    def get_application(self, app_id: str) -> Optional[LoanApplication]:
        return self.apps_store.get_by_id(app_id)

    def get_repayment(self, repayment_id: str) -> Optional[LoanRepayment]:
        return self.repay_store.get_by_id(repayment_id)

















    