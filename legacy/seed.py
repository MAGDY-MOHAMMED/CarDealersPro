import email
from app.models import UserRole

def run_seed(manager) -> None:
    print  ("Starting data seed")
    try :
        # This is a legacy seed script using JSON storage
        # For production, use DB-based seeding with SQLAlchemy
        print("Legacy seed script - use DB-based seeding for production")
    except ValueError as e:
        print(f"Error during seeding: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error during seeding: {e}")
        raise

if __name__ == "__main__":
    print("Legacy seed script - use DB-based seeding for production")
