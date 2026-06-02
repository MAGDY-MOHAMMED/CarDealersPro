from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.models import Car, CarRating, User, LoanApplication, LoanDisbursement, LoanRepayment, Transaction, LoanStatus, PaymentMethod, RepaymentSchedule
from app.models import UserRole
from datetime import timezone
from app.utils.filter_builder import build_filter_query
import asyncio
from app.core.exceptions import NotFoundException, ValidationException
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta ,timezone


def ensure_utc_datetime (datetime: datetime) -> datetime:
    """
    Convert any datetime to a timezone-aware UTC datetime.
    
    - If naive (SQLite), assume it's UTC and attach tzinfo.
    - If aware, convert to UTC.
    """
    if datetime.tzinfo is None:
        return datetime.replace(tzinfo=timezone.utc)
    return datetime.astimezone(timezone.utc)

async def get_filtered_cars(
    db: AsyncSession,
    params: Dict[str, Any],
    limit: int,
    offset: int,
    sort_by: str = "created_at",
    order: str = "desc",
):
    query = select(
        Car,
        User.full_name.label("owner_name"),
        func.count(CarRating.car_id).label("ratings_count"),
        func.avg(CarRating.value_score).label("average_rating"),
    ).join(
        User,
        Car.owner_id == User.id,
        isouter=True,
    ).join(
        CarRating,
        Car.id == CarRating.car_id,
        isouter=True,
    ).where(
        Car.is_deleted.is_(False)
    ).group_by(Car.id, User.id)

    # Use build_filter_query for dynamic filtering and sorting
    query = build_filter_query(
        query,
        Car,
        params,
        search_fields=["brand", "model", "color"],
        sort_by=sort_by,
        order=order
    )

    result = await db.execute(query.limit(limit).offset(offset))
    return result.all()


async def transfer_car_ownership_atomic(
    db: AsyncSession,
    car_id: UUID,
    new_owner_id: UUID,
) -> Car:
    car_result = await db.execute(
        select(Car).where(Car.id == car_id, Car.is_deleted.is_(False)).with_for_update() #prevent the race condition
    )
    car = car_result.scalar_one_or_none()
    if not car:
        raise NotFoundException("Car", str(car_id))
    # Check if the new owner exists
    owner_result = await db.execute(
        select(User).where(or_(User.id == car.owner_id, User.id == new_owner_id)).with_for_update() # to prevent the change of the inventory count
    )
    owners = {user.id: user for user in owner_result.scalars().all()} # create a dictionary of owners
    new_owner = owners.get(new_owner_id)
    if not new_owner:
        raise NotFoundException("User", str(new_owner_id)) # user not found
    # Update inventory count
    old_owner = owners.get(car.owner_id)
    if old_owner and old_owner.role == UserRole.DEALER and old_owner.inventory_count > 0: # prevent negative inventory count
        old_owner.inventory_count -= 1 # decrease the inventory count of the old owner
    if new_owner.role == UserRole.DEALER:
        new_owner.inventory_count += 1 # increase the inventory count of the new owner

    car.owner_id = new_owner_id
    await db.flush() # Commit the transaction to update the inventory count
    await db.refresh(car)
    return car


# Finance Service Layer (MAMAA Grade - DB-level implementation)
class FinanceCalculator:
    @staticmethod
    def calculate_monthly_payment(principal: float, annual_interest_rate: float, months: int) -> float:
        if months <= 0 or annual_interest_rate <= 0:
            return round(principal / (months or 1), 2)
        monthly_rate = (annual_interest_rate / 100) / 12 #for amortaization
        payment = (principal * monthly_rate) / (1 - (1 + monthly_rate) ** -months)
        return round(payment, 2)

    @staticmethod
    def calculate_loan_details(principal: float, annual_interest_rate: float, months: int) -> Dict[str, float]:
        monthly_payment = FinanceCalculator.calculate_monthly_payment(principal, annual_interest_rate, months)
        total_payment = monthly_payment * months
        total_interest = total_payment - principal
        return {
            "monthly_payment": monthly_payment,
            "total_payment": total_payment,
            "total_interest": total_interest
        }

    @staticmethod
    def calculate_custom_interest(car_condition: str, down_payment: float, car_price: float, base_rate: float) -> float:
        # Calculate down payment percentage
        dp_percent = (down_payment / car_price) * 100
        # Reduce interest rate by 1% if down payment > 40%
        if dp_percent > 40:
            base_rate -= 1.0 # Incentive for high down payment
        return base_rate


async def create_loan_application(
    db: AsyncSession,
    client_id: UUID,
    car_id: UUID,
    bank_id: UUID,
    down_payment: float,
    tenure_months: int,
) -> LoanApplication:
    # Validate car exists and is available
    car_result = await db.execute(
        select(Car).where(Car.id == car_id, Car.is_deleted.is_(False)).with_for_update()
    )
    car = car_result.scalar_one_or_none()
    if not car:
        raise NotFoundException("Car", str(car_id))

    if not car.is_available:
        raise ValidationException("Vehicle is not available for sale")

    # Validate client exists
    client_result = await db.execute(
        select(User).where(User.id == client_id).with_for_update()
    )
    client = client_result.scalar_one_or_none()
    if not client:
        raise NotFoundException("User", str(client_id))

    # Validate bank exists
    bank_result = await db.execute(
        select(User).where(User.id == bank_id).with_for_update()
    )
    bank = bank_result.scalar_one_or_none()
    if not bank:
        raise NotFoundException("User", str(bank_id))

    # Validate car condition
    car_condition = car.condition.lower() # data sanitization
    if car_condition not in ["new", "used"]:
        raise ValidationException("Car condition must be 'new' or 'used'")

    # Get bank rates or use defaults
    if car_condition == "new":
        min_dp_percent = bank.bank_min_dp_new if bank.bank_min_dp_new else 15.0 # minimum down payment percentage
        max_months = bank.bank_max_months_new if bank.bank_max_months_new else 60 # maximum tenure in months
        base_interest_rate = bank.bank_rate_new if bank.bank_rate_new else 12.0 # base interest rate
    else:
        min_dp_percent = bank.bank_min_dp_used if bank.bank_min_dp_used else 20.0 # minimum down payment percentage
        max_months = bank.bank_max_months_used if bank.bank_max_months_used else 48 # maximum tenure in months
        base_interest_rate = bank.bank_rate_used if bank.bank_rate_used else 14.0 # base interest rate

    # Validate down payment
    if down_payment < 0 or down_payment >= car.price_consumer: 
        raise ValidationException("Down payment must be non-negative and less than car price")

    required_dp = car.price_consumer * (min_dp_percent / 100) # required down payment
    if down_payment < required_dp:
        raise ValidationException(
            f"Down payment too low. Bank/System requires {min_dp_percent}% ({required_dp:.2f} EGP) for {car_condition} cars."
        )

    # Validate loan term
    if tenure_months <= 0:
        raise ValidationException("Loan term must be greater than zero")
    if tenure_months > max_months:
        raise ValidationException(f"Loan term too long! Maximum for {car_condition} cars is {max_months} months")

    # Validate client income
    if client.monthly_income is None or client.monthly_income <= 0:
        raise ValidationException("Client monthly income must be greater than zero")

    # Calculate loan amount
    loan_amount = car.price_consumer - down_payment

    # Calculate custom interest rate based on down payment
    interest_rate = FinanceCalculator.calculate_custom_interest(
        car_condition, down_payment, car.price_consumer, base_interest_rate
    )

    # Calculate monthly installment
    monthly_installment = FinanceCalculator.calculate_monthly_payment(
        loan_amount, interest_rate, tenure_months
    )

    # Validate debt-to-income ratio (default 40%)
    income_debt_ratio = 0.40
    income_limit = client.monthly_income * income_debt_ratio
    if monthly_installment > income_limit:
        raise ValidationException(
            f"Loan Rejected: Installment {monthly_installment:.2f} exceeds limit ({income_limit:.2f})"
        )

    # Create loan application
    application = LoanApplication(
        client_id=client_id,
        car_id=car_id,
        bank_id=bank_id,
        loan_amount=loan_amount,
        down_payment=down_payment,
        tenure_months=tenure_months,
        interest_rate=interest_rate,
        monthly_installment=monthly_installment,
        status=LoanStatus.PENDING
    )

    db.add(application)
    await db.flush()
    await db.refresh(application)
    return application


async def get_loan_application(
    db: AsyncSession,
    application_id: UUID,
) -> LoanApplication:
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise NotFoundException("LoanApplication", str(application_id))
    return application

#helper function in routes
async def update_loan_application_status(
    db: AsyncSession,
    application_id: UUID,
    status: LoanStatus,
    interest_rate: Optional[float] = None,
) -> LoanApplication:
    result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id).with_for_update()
    )
    application = result.scalar_one_or_none()
    if not application:
        raise NotFoundException("LoanApplication", str(application_id))

    application.status = status # ORM record that the status changed dirty state so we can update it later
    if interest_rate is not None:
        application.interest_rate = interest_rate # For possible changes , Data Consistency
        # Recalculate monthly installment
        application.monthly_installment = FinanceCalculator.calculate_monthly_payment(
            application.loan_amount, interest_rate, application.tenure_months
        )

    # Auto-generate repayment schedule when loan is approved
    if status == LoanStatus.APPROVED:
        try:
            await generate_repayment_schedule(db, application_id)
        except Exception as e:
            # Log error but don't fail the status update
            pass

    await db.flush()
    await db.refresh(application)
    return application


async def get_client_loan_applications(
    db: AsyncSession,
    client_id: UUID,
    status: Optional[LoanStatus] = None,
) -> List[LoanApplication]:
    query = select(LoanApplication).where(LoanApplication.client_id == client_id)
    if status:
        query = query.where(LoanApplication.status == status)
    result = await db.execute(query.order_by(LoanApplication.applied_at.desc()))
    return result.scalars().all()


async def create_loan_disbursement(
    db: AsyncSession,
    application_id: UUID,
    amount: float,
    bank_reference: str,
    notes: Optional[str] = None,
) -> LoanDisbursement:
    # Validate application exists and is approved
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id).with_for_update()
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise NotFoundException("LoanApplication", str(application_id))

    if application.status != LoanStatus.APPROVED:
        raise ValidationException(f"Cannot disburse funds for status: {application.status}")

    if amount <= 0:
        raise ValidationException("Disbursement amount must be positive")

    # Create disbursement
    disbursement = LoanDisbursement(
        application_id=application_id,
        amount=amount,
        bank_reference=bank_reference,
        notes=notes
    )

    # Update application status
    application.status = LoanStatus.DISBURSED

    db.add(disbursement)
    await db.flush()
    await db.refresh(disbursement)
    return disbursement


async def create_loan_repayment(
    db: AsyncSession,
    application_id: UUID,
    amount: float,
    payment_method: str = "E-Wallet",
    reference: Optional[str] = None,
) -> LoanRepayment:
    # Validate application exists
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id).with_for_update()
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise NotFoundException("LoanApplication", str(application_id))

    if amount <= 0:
        raise ValidationException("Repayment amount must be positive")

    # Create repayment
    repayment = LoanRepayment(
        application_id=application_id,
        amount=amount,
        payment_method=payment_method,
        reference=reference
    )

    db.add(repayment)
    await db.flush()
    await db.refresh(repayment)
    return repayment


async def get_loan_repayments(
    db: AsyncSession,
    application_id: UUID,
) -> List[LoanRepayment]:
    result = await db.execute(
        select(LoanRepayment).where(LoanRepayment.application_id == application_id)
        .order_by(LoanRepayment.payment_date.desc()) #newest first
    )
    return result.scalars().all()


async def create_transaction(
    db: AsyncSession,
    buyer_id: UUID,
    seller_id: UUID,
    car_id: UUID,
    amount: float,
    method: PaymentMethod = PaymentMethod.CASH,
    reference: Optional[str] = None,
) -> Transaction:
    # Validate buyer exists
    buyer_result = await db.execute(
        select(User).where(User.id == buyer_id).with_for_update()
    )
    buyer = buyer_result.scalar_one_or_none()
    if not buyer:
        raise NotFoundException("User", str(buyer_id))

    # Validate seller exists
    seller_result = await db.execute(
        select(User).where(User.id == seller_id).with_for_update()
    )
    seller = seller_result.scalar_one_or_none()
    if not seller:
        raise NotFoundException("User", str(seller_id))

    # Validate car exists
    car_result = await db.execute(
        select(Car).where(Car.id == car_id, Car.is_deleted.is_(False)).with_for_update()
    )
    car = car_result.scalar_one_or_none()
    if not car:
        raise NotFoundException("Car", str(car_id))

    if amount <= 0:
        raise ValidationException("Transaction amount must be positive")

    # Create transaction
    transaction = Transaction(
        buyer_id=buyer_id,
        seller_id=seller_id,
        car_id=car_id,
        amount=amount,
        method=method,
        reference=reference
    )

    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)
    return transaction


async def get_user_transactions(
    db: AsyncSession,
    user_id: UUID,
    as_buyer: bool = True,
    as_seller: bool = True,
) -> List[Transaction]:
    conditions = []
    if as_buyer: #if user is buyer
        conditions.append(Transaction.buyer_id == user_id)
    if as_seller: #if user is seller
        conditions.append(Transaction.seller_id == user_id)

    if not conditions:
        return []

    result = await db.execute(
        select(Transaction).where(or_(*conditions)) # (*conditions) means unpacking the list
        .order_by(Transaction.transaction_date.desc()) #newest first
    )
    return result.scalars().all()

# Saga Pattern
async def complete_finance_sale(
    db: AsyncSession,
    application_id: UUID,
    bank_reference: str,
) -> Transaction:
    # Validate application exists
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id).with_for_update()
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise NotFoundException("LoanApplication", str(application_id))

    # Get car
    car_result = await db.execute(
        select(Car).where(Car.id == application.car_id).with_for_update()
    )
    car = car_result.scalar_one_or_none()
    if not car:
        raise NotFoundException("Car", str(application.car_id))

    # Record disbursement
    disbursement = await create_loan_disbursement(
        db, application_id, application.loan_amount, bank_reference
    )

    # Transfer ownership
    await transfer_car_ownership_atomic(db, application.car_id, application.client_id)

    # Create transaction
    transaction = await create_transaction(
        db,
        buyer_id=application.client_id,
        seller_id=car.owner_id,
        car_id=application.car_id,
        amount=application.loan_amount + application.down_payment,
        method=PaymentMethod.FINANCE,
        reference=bank_reference
    )

    return transaction


# Repayment Schedule Service Layer (MAMAA Grade - DB-level implementation)
async def generate_repayment_schedule(
    db: AsyncSession,
    application_id: UUID,
) -> List[RepaymentSchedule]:
    # Get loan application
    app_result = await db.execute(
        select(LoanApplication).where(LoanApplication.id == application_id)
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise NotFoundException("LoanApplication", str(application_id))

    # Calculate amortization schedule
    monthly_rate = (application.interest_rate / 100) / 12 #convert annual rate to monthly rate
    remaining_balance = application.loan_amount #initial remaining balance
    schedules = []

    for month in range(1, application.tenure_months + 1): #month 1 to tenure_months
        # Calculate interest for this month
        interest_amount = remaining_balance * monthly_rate

        # Calculate principal for this month
        principal_amount = application.monthly_installment - interest_amount

        # Update remaining balance
        remaining_balance -= principal_amount #subtract principal from remaining balance

        # Handle final payment rounding , Floating Point Precision means 
        if month == application.tenure_months:
            principal_amount += remaining_balance
            remaining_balance = 0 #set remaining balance to 0

        # Calculate due date (first payment 30 days from approval)
        due_date = application.applied_at + timedelta(days=30 * month) #calculate due date

        schedule = RepaymentSchedule(
            application_id=application_id,
            installment_number=month,
            due_date=due_date,
            amount=application.monthly_installment,
            principal_amount=round(principal_amount, 2),
            interest_amount=round(interest_amount, 2),
            remaining_balance=round(max(0, remaining_balance), 2), #ensure remaining balance is not negative , max(0, remaining_balance) means if remaining_balance is negative, set it to 0
            is_paid=False
        )

        db.add(schedule)
        schedules.append(schedule)

    await db.flush()
    return schedules

#Get repayment schedule, ordered by installment number
async def get_repayment_schedule(
    db: AsyncSession,
    application_id: UUID,
) -> List[RepaymentSchedule]:
    result = await db.execute(
        select(RepaymentSchedule)
        .where(RepaymentSchedule.application_id == application_id)
        .order_by(RepaymentSchedule.installment_number)
    )
    return result.scalars().all()


#Get repayment schedule summary ,for dashboard
async def get_repayment_schedule_summary(
    db: AsyncSession,
    application_id: UUID,
) -> Dict[str, Any]:
    # Get all schedules
    schedules = await get_repayment_schedule(db, application_id)

    if not schedules:
        raise NotFoundException("RepaymentSchedule", str(application_id))

    # Calculate summary
    total_installments = len(schedules)
    paid_installments = sum(1 for s in schedules if s.is_paid) #count paid installments
    remaining_installments = total_installments - paid_installments
    total_amount = sum(s.amount for s in schedules) #sum all installments
    paid_amount = sum(s.paid_amount or 0 for s in schedules if s.is_paid) #sum paid installments , generators so no lists in rams just on the fly   
    remaining_amount = total_amount - paid_amount

    # Find next payment
    next_payment = next((s for s in schedules if not s.is_paid), None)
    next_payment_date = next_payment.due_date if next_payment else None
    next_payment_amount = next_payment.amount if next_payment else None

    # Calculate overdue amount
    today = datetime.now(timezone.utc)
    overdue_amount = sum(
        s.amount for s in schedules
        if not s.is_paid and ensure_utc_datetime(s.due_date) < today
    )
    # for capsulate  the data for the router
    return {
        "application_id": application_id,
        "total_installments": total_installments,
        "paid_installments": paid_installments,
        "remaining_installments": remaining_installments,
        "total_amount": total_amount,
        "paid_amount": paid_amount,
        "remaining_amount": remaining_amount,
        "next_payment_date": next_payment_date,
        "next_payment_amount": next_payment_amount,
        "overdue_amount": overdue_amount
    }

#
async def record_payment_against_schedule(
    db: AsyncSession,
    application_id: UUID,
    amount: float,
    payment_date: Optional[datetime] = None,
    grace_period_days: int = 30

) -> Dict[str, Any]:
    """
    Record payment using waterfall logic (supports partial payments).
    Returns summary of applied amount and updated installments.
    """
    return await record_waterfall_payment(db, application_id, amount, grace_period_days, payment_date)


async def get_unpaid_installments_ordered (
    db : AsyncSession,
    application_id : UUID ) -> List[RepaymentSchedule]:
        """Get all unpaid installments ordered by due date (oldest first)."""
        result = await db.execute(
            select(RepaymentSchedule).where(
                RepaymentSchedule.application_id == application_id,
                RepaymentSchedule.is_paid == False
            ).order_by(RepaymentSchedule.due_date) # Due date is already a datetime object
        )
        #scalars return json objects not sqlalchemy objects , so we can use them in the router
        return result.scalars().all()

async def record_waterfall_payment(
    db: AsyncSession,
    application_id: UUID,
    amount_paid: float, 
    grace_period_days: int = 30,
    payment_date: Optional[datetime] = None, 
) -> Dict[str, Any]:
    """
    Record a payment using waterfall method:
    1. Penalties (overdue fees) – if any
    2. Interest overdue
    3. Principal (starting from oldest unpaid installment)
    4. Partial payment remains as unpaid (marked as overdue)
    """
    payment_date = ensure_utc_datetime(payment_date or datetime.now(timezone.utc))
    schedules = await get_unpaid_installments_ordered(db,application_id) #means get all unpaid installments ordered by due date (oldest first)
    if not schedules :
        raise ValidationException("no pending installments found for this application")
    total_ramaining= sum(s.amount - (s.paid_amount or 0) for s in schedules) #means remaining amount to pay
    if amount_paid <= 0:
        raise ValidationException("payment amount must be positive")
    for schedule in schedules :
        due_date_utc = ensure_utc_datetime(schedule.due_date)
        if due_date_utc < payment_date : # if due date is before payment date
            overdue = (payment_date -due_date_utc).days #number of days overdue
            schedule.overdue_days = max (0, overdue - grace_period_days ) #means number of days overdue after grace period
        else :
            schedule.overdue_days = 0
    remaining = amount_paid
    for schedule in schedules :
        if remaining <= 0 : # if remaining is less than or equal to 0
            break # means no more payment to process
        due_now =round(schedule.amount - (schedule.paid_amount or 0), 2) #means amount due now ,
        if remaining >= due_now : #if remaining is greater than or equal to due now
            schedule.paid_amount = schedule.amount #means fully paid
            schedule.is_paid = True
            schedule.paid_date = payment_date #means payment date
            remaining -= due_now #means remaining amount to pay
            remaining = round (remaining, 2)
        else : #if remaining is less than due now
            schedule.paid_amount = (schedule.paid_amount or 0 ) + remaining
            schedule.is_paid = False
            schedule.paid_date = None # because it is noot fully paid
            remaining = 0
            # Optionally mark as partially paid (you can add a column if needed) so ?
            break
    await db.flush() #means save changes to database
    #if all paid :
    for schedule in schedules:
        await db.refresh(schedule) # to refresh the paid if it disburse a part of it
    all_paid = all(s.is_paid for s in schedules) # all is short circuting , like next and any
    if all_paid :
        app_result = await db.execute(
            select(LoanApplication).where(LoanApplication.id == application_id)
        )
        app = app_result.scalar_one()
        app.status = LoanStatus.PAID_OFF #means loan is paid off
    return {
        "application_id": application_id, #id of the loan application
        "amount_received": amount_paid,
        "amount_applied": amount_paid - remaining, #amount applied to installments
        "remaining_unpaid": remaining, #remaining unpaid amount
        "installments_updated": len([s for s in schedules if s.is_paid or (s.paid_amount or 0) > 0])
    }


    

