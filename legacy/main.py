from core.auth import IdentityManager, UserManager, ClientProfile, DealerProfile, BankProfile
from core.vehicles import InventoryManager
from core.finance import FinanceManager, LoanStatus

def run_system_test() :
    identity =IdentityManager()
    user_manager = UserManager(identity)
    inventory = InventoryManager(user_manager)
    finance = FinanceManager()

    cib_bank = BankProfile.register_new_bank(
        email="info@cib.com",
        bank_name="CIB Egypt",
        swift_code="CIBEGYCX123",
        iban="EG123456789"
    )
    cib_bank.rates = {"new": 12.0, "used": 16.0}
    cib_bank.min_dp_percent = {"new": 15.0, "used": 30.0}
    cib_bank.max_months = {"new": 84, "used": 60}
    identity.register_user(cib_bank) #

    dealer = DealerProfile.register_new_dealer("dealer@cars.com", "AutoTrade", "Ahmed Ali")
    identity.register_user(dealer)

    used_car_data = {
        "vin": "VIN123_USED",
        "make": "Toyota",
        "model": "Corolla",
        "year": 2020,
        "price": 500000.0,
        "condition": "Used" # مستعملة
    }
    car = inventory.add_vehicle(dealer.email, used_car_data)
    client = ClientProfile.create_guest("client@test.com", "Mohamed")
    client.monthly_income = 20000.0 # دخل العميل 20 ألف
    identity.register_user(client) # 
    
    # FINANCE SALE

    print(f"--- Testing Finance for {car.make} {car.model} ({car.condition}) ---")
    try :
        print("\n[Test 2] High Installment (Short Tenure):")
        loan_app =finance.apply_for_loan(client, car, cib_bank, down_payment=200000.0, months=12)           
        print(f" Application Approved! ID: {loan_app.uid}")
        print(f" Installment: {loan_app.monthly_installment} EGP/Month")

        print("\n[Step 2] Processing Bank Disbursement...")
        loan_app.status = LoanStatus.APPROVED 
        finance.complete_finance_sale(loan_app.uid, bank_ref="BANK_REF_55", inventory_manager=inventory) #
    except Exception as e:
        print(f"❌ Finance Error: {e}")
    #cash B2B
    car2 =inventory.add_vehicle(dealer.email, {
        "vin": "VIN_B2B", "make": "BMW", "model": "X5",
        "year": 2023, "price": 3000000.0, "condition": "new"
    })
    another_dealer = DealerProfile.register_new_dealer("dealer2@cars.com", "LuxCars", "Zaid")

    finance.process_cash_sale( another_dealer, car2, inventory, ref="B2B_101")

    updated_car2 = inventory.get_vehicle_by_vin(car2.vin)

    print (f" B2B Done . New Owner : {updated_car2.owner_id} | Status: {updated_car2.status}") 
if __name__ == "__main__":
    run_system_test()