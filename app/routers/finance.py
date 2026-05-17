from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional , Dict
from app.database import get_write_db, get_read_db
from app.schemas import (
    LoanApplicationCreate,
    LoanApplicationResponse,
    LoanApplicationUpdate,
    LoanDisbursementCreate,
    LoanDisbursementResponse,
    LoanRepaymentCreate,
    LoanRepaymentResponse,
    TransactionCreate,
    TransactionResponse,
    FinanceCalculatorRequest,
    FinanceCalculatorResponse,
    RepaymentScheduleResponse,
    RepaymentScheduleSummary,
    PaymentSummaryResponse  
)
from app.services.car_service import (
    FinanceCalculator,
    create_loan_application,
    get_loan_application,
    update_loan_application_status,
    get_client_loan_applications,
    create_loan_disbursement,
    create_loan_repayment,
    get_loan_repayments,
    create_transaction,
    get_user_transactions,
    complete_finance_sale,
    generate_repayment_schedule,
    get_repayment_schedule,
    get_repayment_schedule_summary,
    record_payment_against_schedule,
)
from app.models import LoanStatus
from app.core.request_id import set_request_id, generate_request_id, get_request_id
from app.core.logging_config import logger

router = APIRouter(prefix="/finance", tags=["Finance"])


@router.post("/calculate", response_model=FinanceCalculatorResponse)
async def calculate_loan(
    request: FinanceCalculatorRequest,
):
    """
    Calculate loan details (monthly payment, total payment, total interest)
    """
    details = FinanceCalculator.calculate_loan_details(
        request.principal, request.annual_interest_rate, request.months
    )
    return FinanceCalculatorResponse(**details)


@router.post("/applications", response_model=LoanApplicationResponse, status_code=status.HTTP_201_CREATED)
async def apply_for_loan(
    application_data: LoanApplicationCreate,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Create a new loan application with advanced validation
    """
    try:
        application = await create_loan_application(
            db=db,
            client_id=application_data.client_id,
            car_id=application_data.car_id,
            bank_id=application_data.bank_id,
            down_payment=application_data.down_payment,
            tenure_months=application_data.tenure_months,
        )

        logger.info(
            f"Loan application created: {application.id} with interest rate: {application.interest_rate}%",
            extra={"request_id": get_request_id(), "application_id": str(application.id)}
        )

        return application
    except Exception as e:
        logger.error(
            f"Failed to create loan application: {e}",
            extra={"request_id": get_request_id(), "error": str(e)}
        )
        raise


@router.get("/applications/{application_id}", response_model=LoanApplicationResponse)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_read_db),
):
    """
    Get a loan application by ID
    """
    try:
        application = await get_loan_application(db, application_id)
        return application
    except Exception as e:
        logger.error(
            f"Failed to get loan application: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise


@router.patch("/applications/{application_id}", response_model=LoanApplicationResponse)
async def update_application(
    application_id: UUID,
    update_data: LoanApplicationUpdate,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Update loan application status or interest rate
    """
    try:
        if update_data.status is None and update_data.interest_rate is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either status or interest_rate must be provided"
            )

        application = await update_loan_application_status(
            db=db,
            application_id=application_id,
            status=update_data.status if update_data.status else LoanStatus.PENDING,
            interest_rate=update_data.interest_rate,
        )

        logger.info(
            f"Loan application updated: {application.id}",
            extra={"request_id": get_request_id(), "application_id": str(application.id)}
        )

        return application
    except Exception as e:
        logger.error(
            f"Failed to update loan application: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise


@router.get("/clients/{client_id}/applications", response_model=List[LoanApplicationResponse])
async def get_client_applications(
    client_id: UUID,
    status: Optional[LoanStatus] = None,
    db: AsyncSession = Depends(get_read_db),
):
    """
    Get all loan applications for a client
    """
    try:
        applications = await get_client_loan_applications(db, client_id, status)
        return applications
    except Exception as e:
        logger.error(
            f"Failed to get client loan applications: {e}",
            extra={"request_id": get_request_id(), "client_id": str(client_id), "error": str(e)}
        )
        raise


@router.post("/disbursements", response_model=LoanDisbursementResponse, status_code=status.HTTP_201_CREATED)
async def create_disbursement(
    disbursement_data: LoanDisbursementCreate,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Create a loan disbursement
    """
    try:
        disbursement = await create_loan_disbursement(
            db=db,
            application_id=disbursement_data.application_id,
            amount=disbursement_data.amount,
            bank_reference=disbursement_data.bank_reference,
            notes=disbursement_data.notes,
        )

        logger.info(
            f"Loan disbursement created: {disbursement.id}",
            extra={"request_id": get_request_id(), "disbursement_id": str(disbursement.id)}
        )

        return disbursement
    except Exception as e:
        logger.error(
            f"Failed to create loan disbursement: {e}",
            extra={"request_id": get_request_id(), "error": str(e)}
        )
        raise


@router.post("/repayments", response_model=LoanRepaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_repayment(
    repayment_data: LoanRepaymentCreate,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Create a loan repayment
    """
    try:
        repayment = await create_loan_repayment(
            db=db,
            application_id=repayment_data.application_id,
            amount=repayment_data.amount,
            payment_method=repayment_data.payment_method,
            reference=repayment_data.reference,
        )

        logger.info(
            f"Loan repayment created: {repayment.id}",
            extra={"request_id": get_request_id(), "repayment_id": str(repayment.id)}
        )

        return repayment
    except Exception as e:
        logger.error(
            f"Failed to create loan repayment: {e}",
            extra={"request_id": get_request_id(), "error": str(e)}
        )
        raise


@router.get("/applications/{application_id}/repayments", response_model=List[LoanRepaymentResponse])
async def get_application_repayments(
    application_id: UUID,
    db: AsyncSession = Depends(get_read_db),
):
    """
    Get all repayments for a loan application
    """
    try:
        repayments = await get_loan_repayments(db, application_id)
        return repayments
    except Exception as e:
        logger.error(
            f"Failed to get loan repayments: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise


@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction_record(
    transaction_data: TransactionCreate,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Create a transaction record
    """
    try:
        transaction = await create_transaction(
            db=db,
            buyer_id=transaction_data.buyer_id,
            seller_id=transaction_data.seller_id,
            car_id=transaction_data.car_id,
            amount=transaction_data.amount,
            method=transaction_data.method,
            reference=transaction_data.reference,
        )

        logger.info(
            f"Transaction created: {transaction.id}",
            extra={"request_id": get_request_id(), "transaction_id": str(transaction.id)}
        )

        return transaction
    except Exception as e:
        logger.error(
            f"Failed to create transaction: {e}",
            extra={"request_id": get_request_id(), "error": str(e)}
        )
        raise


@router.get("/users/{user_id}/transactions", response_model=List[TransactionResponse])
async def get_user_transaction_history(
    user_id: UUID,
    as_buyer: bool = True,
    as_seller: bool = True,
    db: AsyncSession = Depends(get_read_db),
):
    """
    Get transaction history for a user
    """
    try:
        transactions = await get_user_transactions(db, user_id, as_buyer, as_seller)
        return transactions
    except Exception as e:
        logger.error(
            f"Failed to get user transactions: {e}",
            extra={"request_id": get_request_id(), "user_id": str(user_id), "error": str(e)}
        )
        raise


@router.post("/applications/{application_id}/complete", response_model=TransactionResponse)
async def complete_finance_transaction(
    application_id: UUID,
    bank_reference: str,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Complete a finance sale (disburse funds and transfer ownership)
    """
    try:
        transaction = await complete_finance_sale(
            db=db,
            application_id=application_id,
            bank_reference=bank_reference,
        )

        logger.info(
            f"Finance sale completed: {transaction.id}",
            extra={"request_id": get_request_id(), "transaction_id": str(transaction.id), "application_id": str(application_id)}
        )

        return transaction
    except Exception as e:
        logger.error(
            f"Failed to complete finance sale: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise


# Repayment Schedule Endpoints (MAMAA Grade - DB-level implementation)
@router.post("/applications/{application_id}/schedule", response_model=List[RepaymentScheduleResponse])
async def create_repayment_schedule(
    application_id: UUID,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Generate repayment schedule for a loan application
    """
    try:
        schedules = await generate_repayment_schedule(db, application_id)

        logger.info(
            f"Repayment schedule generated for application: {application_id}",
            extra={"request_id": get_request_id(), "application_id": str(application_id)}
        )

        return schedules
    except Exception as e:
        logger.error(
            f"Failed to generate repayment schedule: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise


@router.get("/applications/{application_id}/schedule", response_model=List[RepaymentScheduleResponse])
async def get_application_schedule(
    application_id: UUID,
    db: AsyncSession = Depends(get_read_db),
):
    """
    Get repayment schedule for a loan application
    """
    try:
        schedules = await get_repayment_schedule(db, application_id)
        return schedules
    except Exception as e:
        logger.error(
            f"Failed to get repayment schedule: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise


@router.get("/applications/{application_id}/schedule/summary", response_model=RepaymentScheduleSummary)
async def get_schedule_summary(
    application_id: UUID,
    db: AsyncSession = Depends(get_read_db),
):
    """
    Get repayment schedule summary (total, paid, remaining, next payment)
    """
    try:
        summary = await get_repayment_schedule_summary(db, application_id)
        return summary
    except Exception as e:
        logger.error(
            f"Failed to get schedule summary: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise


@router.post("/applications/{application_id}/schedule/payment", response_model=Dict[Str,Any])
async def record_schedule_payment(
    application_id: UUID,
    amount: float,
    grace_period_days: int = 30,
    db: AsyncSession = Depends(get_write_db),
):
    """
    Record payment against repayment schedule using waterfall method.
    Supports partial payments, applies grace period for overdue days.
    """
    try:
        rseult = await record_payment_against_schedule(db, application_id, amount, grace_period_days=grace_period_days)
        logger.info(
            f"Payment recorded for application: {application_id}, amount: {amount}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "amount": amount}
        )
        return PaymentSummaryResponse(**result)
    except Exception as e:
        logger.error(
            f"Failed to record payment: {e}",
            extra={"request_id": get_request_id(), "application_id": str(application_id), "error": str(e)}
        )
        raise # TODO: Raise custom exception

@router.get("/clients/{client_id}/loans/summary")
async def get_client_loans_summary(
    client_id: UUID,
    db: AsyncSession = Depends(get_read_db),
):
    """
    Get summary of all loans for a client (remaining balance, next payments)
    """
    try:
        applications = await get_client_loan_applications(db, client_id)

        summaries = []
        for app in applications:
            try:
                summary = await get_repayment_schedule_summary(db, app.id)
                summaries.append(summary)
            except Exception:
                # Skip if schedule not generated yet
                continue

        return {
            "client_id": str(client_id),
            "total_loans": len(applications),
            "loans": summaries
        }
    except Exception as e:
        logger.error(
            f"Failed to get client loans summary: {e}",
            extra={"request_id": get_request_id(), "client_id": str(client_id), "error": str(e)}
        )
        raise
