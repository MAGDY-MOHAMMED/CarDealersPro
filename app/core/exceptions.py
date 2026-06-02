from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict
from app.core.request_id import get_request_id





 # Helper to convert the data to json
class ErrorResponse(BaseModel):
    """Standardized error response format"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None



class AppException(HTTPException):
    """Custom application exception with standardized format"""
    #the constructor
    def __init__(
        self, # it refers to the instance of the class
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers
        super().__init__(status_code=status_code, detail=message, headers=headers) #call the parent class constructor

    def to_response(self) -> ErrorResponse:
        """Convert exception to standardized response"""
        return ErrorResponse(
            code=self.code,
            message=self.message,
            details=self.details,
            request_id=get_request_id() 
            # why not headers ? beacause it is only on http envelope
        )

 
class NotFoundException(AppException):
    """Resource not found exception"""
    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier: #if identifier is not None
            message += f": {identifier}" # for example: "Car not found: 123"
        super().__init__(
            status_code=404,
            code="NOT_FOUND",
            message=message,
            details={"resource": resource, "identifier": identifier} # the header is automatically set by FastAPI
        )


class BadRequestException(AppException):
    """Bad request exception"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=400,
            code="BAD_REQUEST",
            message=message,
            details=details # the header is automatically set by FastAPI
        )

# oauth2 protocol , some frontend need this header
class UnauthorizedException(AppException):
    """Unauthorized exception"""
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(
            status_code=401,
            code="UNAUTHORIZED",
            message=message,
            headers={"WWW-Authenticate": "Bearer"} # RFC standard
        )


class ForbiddenException(AppException):
    """Forbidden exception"""
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            status_code=403,
            code="FORBIDDEN",
            message=message
        )

#for conflict exception
class ConflictException(AppException):
    """Conflict exception (e.g., duplicate resource)"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=409,
            code="CONFLICT",
            message=message,
            details=details
        )


# for validation exception
class ValidationException(AppException):
    """Validation exception"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=422,
            code="VALIDATION_ERROR",
            message=message,
            details=details
        )


# for internal server exception
class InternalServerException(AppException):
    """Internal server error exception"""
    def __init__(self, message: str = "Internal server error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=500,
            code="INTERNAL_ERROR",
            message=message,
            details=details
        )


# for insufficient storage exception
class InsufficientStorageException(AppException):
    """Insufficient storage exception"""
    def __init__(self, required: int, available: int):
        super().__init__( # means calling the parent class constructor
            status_code=507,
            code="INSUFFICIENT_STORAGE",
            message=f"Insufficient storage space",
            details={
                "required_gb": required / (1024 * 1024 * 1024), # convert bytes to GB
                "available_gb": available / (1024 * 1024 * 1024) # convert bytes to GB
            }
        )
