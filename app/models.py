from .database import Base
from sqlalchemy import Column, Integer, String ,Boolean, DateTime ,text , ForeignKey , Float , CheckConstraint ,Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import column_property, relationship
import uuid
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import ARRAY
import enum

class UserRole(str, enum.Enum):
    CLIENT = "CLIENT"
    DEALER = "DEALER"
    BANK = "BANK"
    INSURANCE = "INSURANCE"
    INSPECTOR = "INSPECTOR"
    ADMIN = "ADMIN"

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
    subscription_plan = Column(
        String,
        nullable=False,
        server_default='FREE'
        )
    inventory_count = Column(
        Integer,
        nullable=False,
        server_default=text('0')
        )

    # Finance-related fields (MAMAA Grade - DB-level implementation)
    monthly_income = Column(
        Float,
        nullable=True,
        server_default=text('0')
    )
    credit_score = Column(
        Integer,
        nullable=True,
        server_default=text('0')
    )
    employment_status = Column(
        String,
        nullable=True
    )
    employment_years = Column(
        Integer,
        nullable=True,
        server_default=text('0')
    )

    # Bank-specific fields (for BANK role users)
    bank_min_dp_new = Column(
        Float,
        nullable=True,
        server_default=text('15.0')  # Default 15% for new cars
    )
    bank_min_dp_used = Column(
        Float,
        nullable=True,
        server_default=text('20.0')  # Default 20% for used cars
    )
    bank_max_months_new = Column(
        Integer,
        nullable=True,
        server_default=text('60')  # Default 60 months for new cars
    )
    bank_max_months_used = Column(
        Integer,
        nullable=True,
        server_default=text('48')  # Default 48 months for used cars
    )
    bank_rate_new = Column(
        Float,
        nullable=True,
        server_default=text('12.0')  # Default 12% for new cars
    )
    bank_rate_used = Column(
        Float,
        nullable=True,
        server_default=text('14.0')  # Default 14% for used cars
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
        nullable=False)
    model = Column (
        String,
        nullable=False)
    color = Column (
        String,
        nullable=True)
    year = Column (
        Integer,
        nullable=False)
    price_consumer = Column (
        Float,
        nullable=False)
    price_dealer = Column (
        Float,
        nullable=False)
    published = Column (
        Boolean,
        nullable=False,
        server_default='True')
    created_at = Column (
        DateTime(timezone=True),
         nullable = False,
         server_default = func.now())
    owner_id = Column(
        UUID (as_uuid=True), #** UUID (as_uuid=True) means that the id is a UUID and not an integer **
        ForeignKey("users.id", ondelete="SET NULL"),  #we write the tablename.id not the classname.id ,** ForeignKey("users.id", ondelete="SET NULL") means that the owner_id is a foreign key to the id in the users table and if the user is deleted, all his cars will have their owner_id set to NULL **
        nullable= True
        ) # now it is required in the route
    owner = relationship("User", back_populates="cars") # back_populates= cars means that the relationship is bidirectional means that when we access car.owner, we get the owner of that car

    #   owner_name = column_property( # this is a virtual column that is not stored in the database but is computed on the fly
    #     select(User.full_name)
    #     .where(User.id == owner_id)
    #     .correlate_except(User) # this is to prevent the query from being correlated with the parent query
    #     .scalar_subquery() # this is to return a single value
    # )

    is_deleted = Column(
        Boolean,
        nullable=False,
        server_default='False')

    # Finance-related fields (MAMAA Grade - DB-level implementation)
    condition = Column(
        String,
        nullable=False,
        server_default='used'
    )
    is_available = Column(
        Boolean,
        nullable=False,
        server_default='True'
    )
    is_inspected = Column(
        Boolean,
        nullable=False,
        server_default='False'
    )
    inspection_report_id = Column(
        UUID(as_uuid=True),
        nullable=True
    )
    external_url = Column(
        String,
        unique=True,
        nullable=True
    )


    # Indexing Strategy (MAMAA Grade)
    __table_args__ = (
        # 1. Composite Index للبحث المتكرر (brand + model + color)
        Index('idx_car_brand_model_color', 'brand', 'model', 'color'),

        # 2. Single Indexes للفلترة الحسابية والترتيب
        Index('idx_car_brand', 'brand'),
        Index('idx_car_color', 'color'),
        Index('idx_car_year', 'year'),
        Index('idx_car_price_consumer', 'price_consumer'),
        Index('idx_car_price_dealer', 'price_dealer'),
        Index('idx_car_published', 'published'),
        Index('idx_car_created_at', 'created_at'),
        Index('idx_car_owner_id', 'owner_id'),
        Index('idx_car_is_deleted', 'is_deleted'),
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
        nullable=False
    )
    media_url = Column(
        String,
        nullable=False
    )
    media_type = Column(
        Enum(MediaType),
        nullable=False)
    file_size = Column(
        Integer,
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

    # Indexing Strategy (MAMAA Grade)
    __table_args__ = (
        # 1. Single Indexes للفلترة والترتيب
        Index('idx_car_media_car_id', 'car_id'),
        Index('idx_car_media_media_type', 'media_type'),
    )


# Finance Models (MAMAA Grade - DB-level implementation)
class LoanStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    DISBURSED = "DISBURSED"
    REPAYING = "REPAYING"
    PAID_OFF = "PAID_OFF"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    FINANCE = "FINANCE"
    B2B_TRANSFER = "B2B_TRANSFER"


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    bank_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    loan_amount = Column(
        Float,
        nullable=False
    )
    down_payment = Column(
        Float,
        nullable=False
    )
    tenure_months = Column(
        Integer,
        nullable=False
    )
    interest_rate = Column(
        Float,
        nullable=False
    )
    monthly_installment = Column(
        Float,
        nullable=False
    )
    status = Column(
        Enum(LoanStatus),
        nullable=False,
        server_default=LoanStatus.PENDING.value,
        index=True
    )
    applied_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    client = relationship("User", foreign_keys=[client_id], backref="loan_applications")
    car = relationship("Car", backref="loan_applications")
    bank = relationship("User", foreign_keys=[bank_id], backref="bank_loans")

    # Indexing Strategy (MAMAA Grade)
    __table_args__ = (
        Index('idx_loan_app_client_id', 'client_id'),
        Index('idx_loan_app_car_id', 'car_id'),
        Index('idx_loan_app_bank_id', 'bank_id'),
        Index('idx_loan_app_status', 'status'),
        Index('idx_loan_app_applied_at', 'applied_at'),
        # Composite index for common queries
        Index('idx_loan_app_client_status', 'client_id', 'status'),
    )


class LoanDisbursement(Base):
    __tablename__ = "loan_disbursements"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    amount = Column(
        Float,
        nullable=False
    )
    bank_reference = Column(
        String,
        nullable=False
    )
    disbursement_date = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    notes = Column(
        String,
        nullable=True
    )

    # Relationships
    application = relationship("LoanApplication", backref="disbursement")

    # Indexing Strategy (MAMAA Grade)
    __table_args__ = (
        Index('idx_loan_disb_app_id', 'application_id'),
        Index('idx_loan_disb_date', 'disbursement_date'),
    )


class LoanRepayment(Base):
    __tablename__ = "loan_repayments"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    amount = Column(
        Float,
        nullable=False
    )
    payment_method = Column(
        String,
        nullable=False,
        server_default="E-Wallet"
    )
    payment_date = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    reference = Column(
        String,
        nullable=True
    )

    # Relationships
    application = relationship("LoanApplication", backref="repayments")

    # Indexing Strategy (MAMAA Grade)
    __table_args__ = (
        Index('idx_loan_repay_app_id', 'application_id'),
        Index('idx_loan_repay_date', 'payment_date'),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    buyer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True
    )
    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="SET NULL"),
        nullable=False,
        index=True
    )
    amount = Column(
        Float,
        nullable=False
    )
    method = Column(
        Enum(PaymentMethod),
        nullable=False,
        index=True
    )
    reference = Column(
        String,
        nullable=True
    )
    transaction_date = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Relationships
    buyer = relationship("User", foreign_keys=[buyer_id], backref="purchases")
    seller = relationship("User", foreign_keys=[seller_id], backref="sales")
    car = relationship("Car", backref="transactions")

    # Indexing Strategy (MAMAA Grade)
    __table_args__ = (
        Index('idx_transaction_buyer_id', 'buyer_id'),
        Index('idx_transaction_seller_id', 'seller_id'),
        Index('idx_transaction_car_id', 'car_id'),
        Index('idx_transaction_method', 'method'),
        Index('idx_transaction_date', 'transaction_date'),
        # Composite index for common queries
        Index('idx_transaction_buyer_date', 'buyer_id', 'transaction_date'),
        Index('idx_transaction_seller_date', 'seller_id', 'transaction_date'),
    )


class RepaymentSchedule(Base):
    __tablename__ = "repayment_schedules"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    installment_number = Column(
        Integer,
        nullable=False,
        index=True
    )
    due_date = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    amount = Column(
        Float,
        nullable=False
    )
    principal_amount = Column(
        Float,
        nullable=False
    )
    interest_amount = Column(
        Float,
        nullable=False
    )
    remaining_balance = Column(
        Float,
        nullable=False
    )
    is_paid = Column(
        Boolean,
        nullable=False,
        server_default='False',
        index=True
    )
    paid_date = Column(
        DateTime(timezone=True),
        nullable=True
    )
    paid_amount = Column(
        Float,
        nullable=True
    )
    overdue_days = Column(
        Integer,
        nullable=True,
        server_default=text('0')
    )

    # Relationships
    application = relationship("LoanApplication", backref="repayment_schedule")

    # Indexing Strategy (MAMAA Grade)
    __table_args__ = (
        Index('idx_repay_schedule_app_id', 'application_id'),
        Index('idx_repay_schedule_due_date', 'due_date'),
        Index('idx_repay_schedule_is_paid', 'is_paid'),
        # Composite index for common queries
        Index('idx_repay_schedule_app_due', 'application_id', 'due_date'),
        Index('idx_repay_schedule_app_paid', 'application_id', 'is_paid'),
    )

class CarFeatures(Base):
    __tablename__ = "car_features"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    car_id = Column(UUID(as_uuid=True), ForeignKey("cars.id", ondelete="CASCADE"), nullable=False, unique=True)
    feature_vector = Column(ARRAY(Float), nullable=True) # for similarity search
    predicted_price = Column(Float, nullable=True) # for price prediction
    damage_score = Column(Float, nullable=True) # for damage detection
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) # for tracking updates