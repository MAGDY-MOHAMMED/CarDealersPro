from dataclasses import dataclass,field,fields
from typing import List,Dict,Any,Optional
from datetime import datetime
import uuid
from core.auth import UserManager, IdentityManager,UserRole
from core.base import BaseSchema,StorageMixin
from core.config import VEHICLE_CATEGORIES, SUPPORTED_CURRENCIES

@dataclass
class VEHICLE (BaseSchema) :
    vin: str  = ""
    make: str = ""
    model: str = ""
    year: int = 0
    price: float = 0.0
    owner_id : str = ""
    currency: str = "EGP"
    mileage: int = 0
    engine_capacity: str = "" 
    transmission: str = "Automatic" 
    fuel_type: str = "Gasoline" 
    color: str = ""
    category: str = "car" 
    condition: str = "New" 
    is_available: bool = True
    status: str = "AVAILABLE"
    is_inspected: bool = False
    inspection_report_id: Optional[str] = None
    images: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.now) # Last update timestamp
    def __post_init__ (self) :
        super().__post_init__()
        if self.category not in VEHICLE_CATEGORIES :
            self.category = "car"
        if self.currency not in SUPPORTED_CURRENCIES :
            self.currency = "EGP"
        if self.year > datetime.now().year:
            raise ValueError("Year cannot be in the future")
        if self.price < 0:
            raise ValueError("Price cannot be negative")
        if self.mileage < 0:
            raise ValueError("Mileage cannot be negative")
    def upadate_price (self, new_price : float) -> None:
        self.price = round (new_price,2) # round the price to 2 decimal places
        self.updated_at = datetime.now() # update the updated_at timestamp
        self.sync_data() # update the extra data

    def to_dict (self) -> Dict[str, Any]:
        return self.extra_data
    
    @classmethod
    def from_dict (cls, data: Dict[str, Any]) -> 'VEHICLE':
        valid_fields = {f.name for f in fields(cls) if f.init} # Get all field names that are initialized to protect the system 
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}   # Filter out any keys that aren't in the class fields
        return cls(**filtered_data) # Create a new instance with the filtered data # "**" is instead of data['vin'], data['make'], data['model'], etc.


class InventoryManager :  # add or delete or get data 
    # mange the ineventory of vehicles
    def __init__(self, user_manager : UserManager) -> None:
        self.storage = StorageMixin(VEHICLE, "vehicles.json")
        self.vehicles = self.storage.data # Dictionary to store vehicles by VIN
        self.user_manager=user_manager
    def save_to_disk(self):
        self.storage.save() 
    def validate_vehicle_data(self,data: Dict[str, Any]) -> bool: # Validate the vehicle data
        required_fields = ["vin", "make", "model", "year","price"] # Required fields for a vehicle # without owner_id we cannot identify who have the car # ther is no car without vin 
        return all (field in data and data [field] for field in required_fields)

    def add_vehicle(self, dealer_email: str, vehicle_data: Dict[str, Any]) -> VEHICLE:
        user = self.user_manager.identity_manager.get_by_email(dealer_email)
        if not user or str(user.role).upper() != "DEALER":
            raise PermissionError ("Access denied: Only dealers can add vehicles") # Check if the user is a dealer
        vehicle_data['owner_id'] = user.uid 
    
        if not self.validate_vehicle_data(vehicle_data): # Validate the vehicle data
            raise ValueError("Missing fields")
        
        if not self.validate_vehicle_data(vehicle_data):
            raise ValueError("Missing required vehicle fields (vin, make, model, year, price)") # Validate the vehicle data
        current_count = getattr(user, "inventory_count", 0)
        if current_count >= 10:
            raise ValueError("Maximum vehicle limit (10) reached for this dealer") # Check if the user has reached the maximum vehicle limit
        try:
            new_vehicle = VEHICLE.from_dict(vehicle_data)
            if new_vehicle.vin in self.vehicles:
                raise ValueError(f"Vehicle with VIN {new_vehicle.vin} already exists")
            self.vehicles[new_vehicle.vin] = new_vehicle
            user.inventory_count = current_count + 1 # update the inventory count after adding the vehicle
            self.user_manager.update_user(user.email, user)
            return new_vehicle
        except Exception as e:
            raise ValueError(f"Schema Validation Error: {e}") # raise the error to the caller
    def transfer_ownership (self, vin : str ,new_owner_id : str ):
        vehicle = self.get_vehicle_by_vin(vin)
        if not vehicle : 
            raise KeyError(f"Vehicle with VIN {vin} not found.")
        old_owner = vehicle.owner_id
        vehicle.owner_id = new_owner_id
        vehicle.updated_at = datetime.now()
        self.save_to_disk()
        print(f"[Ownership Transfer] VIN {vin} moved from {old_owner} to {new_owner_id}")
        return vehicle
            



    def get_vehicle_by_vin(self, vin: str) -> Optional["VEHICLE"]: # Get a vehicle by VIN
        return self.vehicles.get(vin)

    def get_all_vehicles(self) -> List["VEHICLE"]: # Get all vehicles
        return list(self.vehicles.values()) # Return a list of all vehicles



class VehicleSearch: # logic for feltering  
    def __init__(self, inventory_manager: InventoryManager) -> None:
        """
        Initialize the VehicleSearch with an InventoryManager.
        
        Args:
            inventory_manager: The InventoryManager instance to use for searching vehicles
        """
    
        self.inventory_manager = inventory_manager # Reference to the InventoryManager instance
    def search (self,**criteria ) ->List ["VEHICLE"] :
        results = self.inventory_manager.get_all_vehicles() #
        for key , value in criteria.items() : 
            if value is None : continue
            if key.endswith(('_min','_max'))  :
                is_min= key.endswith('_min')
                field= key.replace('_min','').replace('_max','') # Remove _min or _max from the key
                try :
                    value= float(value) # Convert the value to a float to prevent the TypeError
                    if is_min :
                        results =[ v for v in results if float (getattr(v,field,0)) >= value]
                    else :
                        results =[ v for v in results if float (getattr(v,field,0)) <= value]
                except (ValueError,TypeError) :
                    continue
            else :
                search_value = str(value).strip().lower()
                results = [ v for v in results if str (getattr(v,key,v.extra_data.get(key,""))).strip().lower() == search_value ] 
        return results
    def find_by_vin (self,vin:str) -> Optional["VEHICLE"] :
        return self.inventory_manager.get_vehicle_by_vin(vin) # 

     
    

@dataclass
class VehicleFilter:
    def __init__(self, **criteria: Dict[str, Any]) -> None:
        self.criteria = criteria
    def apply (self , vehicles: List["VEHICLE"]) -> List["VEHICLE"]:
        results = vehicles
        for key, required_value in self.criteria.items(): # Loop through each criterion
            if required_value is None : continue
            filtered = []
            for v in results :
                actual_value = getattr(v,key,v.extra_data.get(key,""))
                if str (actual_value).lower()== str (required_value).lower() : # Check if the actual value matches the required value
                    filtered.append(v)
            results = filtered
        return results


def main():
    identity= IdentityManager()
    user_manager = UserManager(identity)
    inventory = InventoryManager(user_manager)
    search = VehicleSearch(inventory)
    print(search.search(make="Toyota", model="Camry"))

if __name__ == "__main__":
    main()









