from asyncio import gather
from dataclasses import dataclass, field
from typing import Dict, List, Any, Type, TypeVar, Generic, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel as PydanticBaseModel
from pydantic import field_validator
from core.request_id import get_request_id
from core.logging_config import logger
import uuid
import json
import os
import shutil # this for 
from dataclasses import asdict 

T = TypeVar('T', bound = 'BaseSchema')
class StorageMixin(Generic[T]) : # generic class for storage operations in any class 
    def __init__ (self, schema_cls : Type[T] , file_name: str) :
        self.schema_cls = schema_cls
        self.storage_path = os.path.join("data", "json_store", file_name)
        self.data : Dict [str, T] = {}
        self._initialize_storage()
        self.load()
    def _initialize_storage (self) :
        if not os.path.exists((os.path.dirname(self.storage_path))) : # create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path): # create file if it doesn't exist file for what ?
            with open(self.storage_path, "w") as f :
                json.dump({}, f)
    def save (self) -> None :
        temp_path =f"{self.storage_path}.tmp"
        try :
            with open(temp_path, "w",encoding='utf-8') as f : 
                serialized_data= {uid :obj.to_dict() for uid ,obj in self.data.items()} # convert to dict
                json.dump(serialized_data, f, indent=4, ensure_ascii=False) # ascii means ascii characters only
            shutil.move(temp_path, self.storage_path) # atomic operation means if the operation fails, the original file is not lost

        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Critical Failure in Persistence Layer: {e}",extra= {"request_id": get_request_id()})
            raise IOError(f"Critical Failure in Persistence Layer: {e}")
    def load (self) -> None : # load the 
        if not os.path.exists(self.storage_path) :
            return
        try :
            with open(self.storage_path, "r", encoding='utf-8') as f :
                raw_data = json.load(f)
                self.data = {uid : self.schema_cls(**item_data) for uid ,item_data in raw_data.items()} # convert to object
        except (json.JSONDecodeError, TypeError) as e: #JSONDecodeError is a built-in exception in Python, TypeError is a built-in exception in Python 
            logger.error(f"Critical Failure in Persistence Layer: {e}",extra= {"request_id": get_request_id()})
            raise IOError(f"Critical Failure in Persistence Layer: {e}") #IOError is a built-in exception in Python
    def find_by (self, **kwargs : Dict[str, Any]) -> List [T] : # find items by attributes
        def match (obj : T ) -> bool :
            return all (getattr (obj, k, obj.extra_data.get(k)) == v for k,v in kwargs.items()) # check if all the attributes match the values
        return [item for item in self.data.values() if match(item)] # return the items that match the attributes
    def get_by_id(self, uid: str) -> Optional[T]: # quick access for id o (1)
        return self.data.get(uid)

@dataclass
class BaseModel : # automated clening data 
    extra_data : Dict[str, Any] = field(default_factory=dict)
    def format_value (self,value : Any) -> Any :
        if isinstance(value, str):
            return value.strip().lower()
        return value

    def sync_data (self) : # the cleaner
        for f in fields (self) : # get all the fields in the class
            if f.name == "extra_data" : continue # skip the extra data
            val = getattr(self, f.name) # get the value of the field
            clean_val = self.format_value(val) # format the value
            setattr(self, f.name, clean_val) # update the original object
            self.extra_data[f.name] = clean_val # update the extra data
        
        
    def to_dict (self) -> Dict[str,Any] : #
        return self.extra_data # return the extra data
    def __post_init__ (self) -> None: 
        self.sync_data()     # 



@dataclass
class BaseSchema (BaseModel) : # for api responses # to generate uid to any thing to the system
    uid : Optional [str]  = None # in dataclass  there is no thing called init= None so
    created_at : datetime = field(default_factory=datetime.now)
    def __post_init__ (self) -> None:
        if not self.uid:
            self.uid = str(uuid.uuid4()) # generate a unique id because we need it for the api responses and python donot ask for uid when we create that object (not in the init) so we need to generate it manually here
        if isinstance(self.created_at, str): # 
            self.created_at = datetime.fromisoformat(self.created_at) # 
    def to_dict (self) -> Dict[str,Any] :
        return {k: self.format_value(v) for k, v in asdict(self).items()} # return the extra data
    def to_json (self) ->str :
        return json.dumps (self.to_dict(),indent= 4 ) #dumps and indient 
    @classmethod
    def from_json (cls,json_str : str ):
        data=json.loads(json_str) # load the json string
        return cls (**data) # create a new object from the json string


class PydanticBaseSchema (PydanticBaseModel) : # for api responses
    class Config : 
        arbitrary_types_allowed = True # allow arbitrary types
        json_encoders = {datetime: lambda v: v.isoformat()} # encode datetime as iso format
        validate_assignment =True # validate assignment
    def to_dict(self) -> Dict [str, Any] :
        return self.dict() 








