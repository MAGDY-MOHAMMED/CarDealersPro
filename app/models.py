from .database import Base
from sqlalchemy import Column, Integer, String ,Boolean, DateTime ,text , ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid


class User (Base):
    __tablename__ = "users"

    id = Column(
        UUID (as_uuid=True), 
        primary_key= True,
        default=uuid.uuid4, 
        server_default=text("gen_random_uuid()")
        )
    email = Column(
        String, 
        nullable=False, 
        unique=True,
        index= True)
    hashed_password = Column(String, nullable=False)
    cars= relationship("Car", back_populates="owner") # back_populates= owner means that the relationship is bidirectional means that when we access User.cars, we get all cars of that user
    created_at = Column(
        DateTime(timezone=True),
         nullable=False, 
         server_default=func.now())
    is_active = Column(
        Boolean,
        nullable=False,
        server_default='True'
        )
    full_name = Column(
        String,
        nullable=False 
        )
     
     

class Car (Base) :
    __tablename__ = "cars"

    id = Column(
        UUID (as_uuid=True), 
        primary_key= True,
        default=uuid.uuid4, 
        nullable = False, 
        server_default=text("gen_random_uuid()")
        )
    brand = Column (
        String, 
        nullable= False)
    model = Column (
        String, 
        nullable= False)
    year = Column (
        Integer, 
        nullable= False) 
    price = Column (
        Integer, 
        nullable= False)
    published = Column (
        Boolean, 
        nullable = False, 
        server_default = 'True'
        )
    created_at = Column (
        DateTime(timezone=True),
         nullable = False, 
         server_default = func.now()) # server_default = text ('NOW()') or server_default = func.now() ? 
    owner_id = Column(
        UUID (as_uuid=True), #** UUID (as_uuid=True) means that the id is a UUID and not an integer ** 
        ForeignKey("users.id", ondelete="SET NULL"),  #we write the tablename.id not the classname.id ,** ForeignKey("users.id", ondelete="SET NULL") means that the owner_id is a foreign key to the id column in the users table and if the user is deleted, all his cars will have their owner_id set to NULL ** 
        nullable= True,
        index=True #** index=True means that the column will be indexed for faster queries **
        ) # now it is required in the route
    owner = relationship("User", back_populates="cars") # back_populates= cars means that the relationship is bidirectional means that when we access car.owner, we get the owner of that car

    is_deleted = Column(
        Boolean,
        nullable=False,
        server_default='False'
        )
