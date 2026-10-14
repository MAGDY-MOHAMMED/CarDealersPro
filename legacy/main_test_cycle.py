import os
from datetime import datetime
from core.auth import IdentityManager, DealerProfile, InspectorProfile, ClientProfile, BankProfile , UserManager
from core.vehicles import InventoryManager
from core.inspection import InspectionManager
from core.finance import FinanceManager, LoanStatus
from core.config import FINANCE_CONFIG
import traceback


class StorageService :
    BASE_DIR = "storage" #
    UPLOAD_DIR =os.path.join (BASE_DIR, "uploads" ) #

    @classmethod
    def init_storage (cls) : # local folders later may be in s3 config. what is s3 config ? 
        for sub in ["images","videos"] :
            path = os.path.join(cls.UPLOAD_DIR, sub) # join here means concatenate the paths
            if not os.path.exists(path) : #if path doesnot exist
                os.makedirs(path)
    
    @classmethod
    def upload_mock_file (cls ,file_name :str, category : str) -> str :
        cls.init_storage()
        return f"http://localhost/storage/uploads/{category}/{file_name}" 
    
def run_full_business_cycle () :
    identity = IdentityManager()
    user = UserManager(identity)
    inventory = InventoryManager(user_manager=user)
    inspection = InspectionManager(inventory_manager=inventory)
    finance = FinanceManager()
    print("\n" + "="*50)
    print(" STARTING FULL AUTO-SYSTEM TEST CYCLE")
    print("="*50)
    dealer = DealerProfile.register_new_dealer(email= "dealer@example.com",company_name="Abu Shousha Motors", full_name="Magdy Mohamed Abu Shousha", tax_id="12345678901")
    identity.register_user(dealer) # must sign in the system first
    inspector = InspectorProfile(email="eng_ahmed@check.com", full_name="Ahmed Engineering", specialization=["Mechanic", "Electrical"])
    identity.register_user(inspector) # must sign in the system first
    client = ClientProfile.create_guest("client@test.com", "Omar")
    client.monthly_income = 60000.0
    bank = BankProfile(email="national_bank@bank.com", bank_name="NBE", swift_code="NBEGEGCX")
    bank.rates = {"new": 12.0, "used": 15.0}

    car_data = {
        "vin": "EGY-789-V6",
        "make": "toyota",
        "model": "Fortuner",
        "year": 2024,
        "price": 2500000.0,
        "condition": "new"
    }
    car = inventory.add_vehicle(dealer.email, car_data)
    print(f" STEP 1: Vehicle {car.make} {car.model} listed by Dealer.") # make means 
    media_links = [
        StorageService.upload_mock_file("front_view.jpg", "images"),
        StorageService.upload_mock_file("engine_start.mp4", "videos")
    ]
    print(" AI is analyzing video frames and audio...")
    mock_scores = {
        "engine": 85.0,
        "body": 90.0,
        "electrical": 95.0,
        "interior": 100.0,
        "suspension": 80.0
    } 
    report = inspection.submit_report(inspector.email, car.vin, mock_scores, "Perfect condition, sound is clean.")
    print(f" STEP 2: Inspection Report Generated. Score: {report.final_score}%")

    try :
        print(f"\n--- Processing Financing for {client.full_name} ---")
        loan_app = finance.apply_for_loan(
            client=client,
            vehicle=car,
            bank=bank,
            down_payment=500000.0, # 20% دفعة مقدمة
            months=60
        )
        if loan_app :
            print(f"✅ STEP 3: Loan Application Submitted. Status: {loan_app.status}")
            print(f"   - Installment: {loan_app.monthly_installment} EGP")
            print(f"   - Bank Status: {loan_app.status.value}") # Approved, Rejected, Pending
            loan_app.status = LoanStatus.APPROVED 
            finance.complete_finance_sale(loan_app.uid, inventory, bank_ref="TXN-BANK-1122") #
            final_car = inventory.get_vehicle_by_vin(car.vin) #
            print(f"\n✅ STEP 4: TRANSACTION COMPLETED")
            print(f"   - New Owner: {final_car.owner_id}") 
            print(f"   - Car Status: {final_car.status}") # what is the defference between that and line 77 ? 
        else : 
            print("❌ STEP 3: Loan Application Failed")
    except Exception as e:
        print(f"❌ Business Logic failed : {e}")
        traceback.print_exc() # print the full error stack trace

if __name__ == "__main__":
    run_full_business_cycle ()
        