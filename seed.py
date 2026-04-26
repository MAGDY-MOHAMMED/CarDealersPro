import email
from core.auth import (
    IdentityManager,  DealerProfile, UserRole,
    AdminProfile,BankProfile,InspectorProfile)

def run_seed(manager : IdentityManager) -> None:
    print  ("Starting data seed")
    try :

        cib_bank = BankProfile.register_new_bank(
            bank_name="CIB Bank",
            email = "cib@cib.com",
            swift_code="CIBEGYCA",
            iban="EG12345678901234567890123456",
        )
        cib_bank.extra_data.update ({   # until i get to the db
            "address" : "Cairo, Egypt",
            "website" : "https://www.cib.com.eg",
            "status" :  " Active", 
            "created_by" : "System",
            "created_at" : "2025-01-01",
            "updated_by" : "System",
            "updated_at" : "2025-01-01",

        })
            
        
        cib_bank.is_verified= True
        manager.register_user(cib_bank)
        print (" Bank registered")

        elite_dealer = DealerProfile.register_new_dealer(
            email = "elite@elite.com",
            company_name="Elite Dealer",
            full_name = "Elite Dealer",
        )
        elite_dealer.extra_data.update({
            # until i get to the db
            "address" : "Cairo, Egypt",
            "website" : "https://www.elite.com",
            "status" :  " Active", 
            "created_by" : "System",
            "created_at" : "2025-01-01",
            "updated_by" : "System",
            "updated_at" : "2025-01-01",

        })
        elite_dealer.is_verified= True
        manager.register_user(elite_dealer)
        print (" Dealer registered")

        Mechanic_Person=InspectorProfile.register_new_inspector(
            full_name="Mechanic Person",
            email = "mechanic@mechanic.com"
        )

        Mechanic_Person.extra_data.update({
            # until i get to the db
            "address" : "Cairo, Egypt",
            "website" : "https://www.mechanic.com",
            "status" :  " Active", 
            "created_by" : "System",
            "created_at" : "2025-01-01",
            "updated_by" : "System",
            "updated_at" : "2025-01-01",
            "phone" : "01000000000",
            "first_name":"Mechanic",
            "last_name":"Person",
            "password": "Mechanic123456",
            "inspector_license": "12345678901234",
            "inspector_license_image": "https://www.mechanic.com/mechanic.jpg",
            "inspector_license_expiry": "2025-01-01",
            "inspector_license_status":"Active",
            "inspector_license_notes":"Mechanic Person",
            "inspector_license_created_by":"System",
            "inspector_license_created_at":"2025-01-01",
            "inspector_license_updated_by":"System",
            "inspector_license_updated_at":"2025-01-01",
        })

        
        Mechanic_Person.is_verified= True
        manager.register_user(Mechanic_Person)
        print(f"Seeding Completed! the number of users in system is {len(manager.users)}")
    except ValueError as e:
        print(f"Error during seeding: {e}")
        raise # to see the error in the console
    except Exception as e:
        print(f"Unexpected error during seeding: {e}")
        raise # to see the error in the console

if __name__ == "__main__":
    test_manager= IdentityManager()
    run_seed(test_manager)

    print ("/n"+ "="*40) # separator
    print ("System Statistics")
    print ("-"*40) # separator

    print(f" Banks found : {len(test_manager.find_users(role=UserRole.BANK))}")
    print(f" Dealers found : {len(test_manager.find_users(role=UserRole.DEALER))}")
    print(f" Inspectors found : {len(test_manager.find_users(role=UserRole.INSPECTOR))}")
    print(f" Admins found : {len(test_manager.find_users(role=UserRole.ADMIN))}")
    ciaro_users = test_manager.find_users( address ="Cairo, Egypt")
    print(f" Users in cairo is : {len(ciaro_users)}")
    

