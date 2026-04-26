print("!!!!!!!!!! I AM WORKING FROM THE CORRECT FILE !!!!!!!!!!")
from email.policy import default
from dataclasses import  dataclass , field
from typing import Dict,List,Tuple
from datetime import datetime
from core.base import BaseSchema, StorageMixin
from core.config import  INSPECTOR_SPECIALIZATIONS , default_categories
from enum import Enum, auto


class MediaType (Enum) :
    IMAGE = auto () 
    VIDEO = auto ()
@dataclass () # why () ? 
class MediaFile :
    media_type: MediaType 
    label : str = "" # like "Engine Sound", "Exterior Left", "Dashboard" or 
    file_path : str = ""



@dataclass()
class  InspectionReport (BaseSchema) :
    vin : str =""
    inspector_id : str = ""
    media_files : List [MediaFile] = field (default_factory= list) # list of multimedia 
    scores : dict [str,float ] = field (default_factory= lambda : { 
        "engine" : 0, "body" : 0 , "electrical" : 0 , "interior" : 0 , "suspension" : 0 })
    acoustic_report : str = ""
    notes : str = ""
    final_score : float =0.0 # 
    is_passed : bool = False 
    def __post_init__(self):
        super().__post_init__()
        self.final_score ,self.is_passed = self.calculate_rating(self.scores)
    @staticmethod
    def calculate_rating (score : Dict [str, float]) -> Tuple[float,bool ]: #Rating Engine: ميثود منفصلة تماماً لإدارة منطق الحساب. لو غيرت الأوزان هنا، الداتا القديمة في الـ JSON هتبقى محفوظة بـ final_score بتاعها.
        weighs = {
            "engine" : 0.35 , "body" : 0.25 , "electrical" : 0.15 , "interior" : 0.15 , "suspension" : 0.10 }
        total = sum (score.get(key,0) * weighs.get(key,0) for key in weighs) # means for each key in weighs, get the score and multiply it by the weight
        return total , (total >= 60.0 ) # 

class InspectionManager :
    def __init__(self , inventory_manager) :
        self.reports_store = StorageMixin(InspectionReport, "inspection_reports.json")
        self.inventory = inventory_manager
    def submit_report (self, inspector_email : str, vin : str , scores : Dict [str,float] ,notes : str = "") :
        vehicle = self.inventory.get_vehicle_by_vin(vin)  # does the car exist ?
        if not vehicle:
            raise ValueError("Vehicle not found")
        report = InspectionReport(
            vin=vin,
            inspector_id=inspector_email, #
            scores=scores,
            notes=notes
        )
        vehicle.is_inspected = True
        vehicle.inspection_report_id = report.uid
        vehicle.extra_data["ai_final_score"] = report.final_score   
        self.reports_store.data[report.uid]=report # why adding uid after add final score ? because we need to access the report by uid
        self.reports_store.save()        
        self.inventory.save_to_disk() # why self.inventory not data or self .reports_store.data ? because we need to save the vehicle data
        return report
