from .database import Base
from sqlalchemy import Column, Integer, String ,Boolean, DateTime ,text , ForeignKey , Float , CheckConstraint ,Enum
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import column_property, relationship
import uuid
from pydantic import BaseModel, Field
from sqlalchemy import select
from core.auth import UserRole
import enum


class MediaType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"  

class User (Base):
    __tablename__ = "users"

    id = Column(
        UUID (as_uuid=True), 
        primary_key= True,
        default=uuid.uuid4, 
        server_default=text("gen_random_uuid()")
        )
    role = Column( # Client , bank , Inspector , Dealer
        Enum(UserRole),
        nullable=False,
        server_default=UserRole.CLIENT.value # default role is client , postrge stores enum as string
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
    color = Column (
        String, 
        nullable= True)
    year = Column (
        Integer, 
        nullable= False) 
    price_consumer = Column (
        Float, 
        nullable= False)
    price_dealer = Column (
        Float, 
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

    owner_name = column_property( # this is a virtual column that is not stored in the database but is computed on the fly
        select(User.full_name)
        .where(User.id == owner_id)
        .correlate_except(User) # this is to prevent the query from being correlated with the parent query
        .scalar_subquery() # this is to return a single value
    )

    is_deleted = Column(
        Boolean,
        nullable=False,
        server_default='False'
        )


class CarRating (Base) :
    __tablename__ = "car_ratings"
    
    user_id = Column (
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True
    )
    car_id = Column (
        UUID(as_uuid=True),
        ForeignKey("cars.id"),
        primary_key=True
    )
    value_score = Column(
        Integer, 
        nullable=False
    )

    comment = Column(
        String,
        nullable=True
    )
    is_ai_generated = Column(
        Boolean, 
        default=False
    )
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    # here we are using __table_args__ to add a check constraint to the table
    __table_args__ = (
        CheckConstraint(
            'value_score >= 0 AND value_score <= 100', #to ensure the value score is between 0 and 100
            name='check_value_score_range' #to name the check constraint
        ),
    )

class UserRating(Base):
    __tablename__ = "user_ratings"

    #
    rater_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"), 
        primary_key=True
    )
    #
    target_user_id = Column( 
        UUID(as_uuid=True),
        ForeignKey("users.id"), 
        primary_key=True
    )

    trust_score = Column(# 0 to 100 
        Integer, nullable=False
        )
    #review text for the trust score
    review_text = Column(
        String,
        nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now())
    #time to check constraints
    __table_args__ = (
        CheckConstraint(
            'trust_score >= 0 AND trust_score <= 100',
            name='check_trust_score_range'
        ), #to ensure the trust score is between 0 and 100
        CheckConstraint(
            'rater_id != target_user_id',
            name='check_not_self_rating'
        ), #to prevent the user to rate himself
    )


class CarMedia(Base):
    __tablename__ = "car_media"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    media_url = Column(
        String,
        nullable=False
    )
    media_type = Column(
        Enum(MediaType),
        nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    car = relationship("Car", backref="media") # backref is used to access the media from the car object

    car_name = column_property( # this is a virtual column that is not stored in the database
        select(Car.brand + ' ' + Car.model)
        .where(Car.id == car_id)
        .correlate_except(Car) # to prevent the query from being correlated with the CarMedia table
        .scalar_subquery() # to return a single value
    )
