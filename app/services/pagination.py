from typing import Generic, TypeVar, List, Any
from pydantic import BaseModel
from sqlalchemy import Select, func, select as sql_select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')

# class for standardized paginated response format
class PaginatedResponse(BaseModel, Generic[T]): # Generic[T] for beautiful docs or swagger 
    """Standardized paginated response format"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


# function to apply pagination to a SQLAlchemy query
def paginate_query(
    query: Select,
    page: int = 1,
    page_size: int = 10,
    max_page_size: int = 100
) -> tuple[Select, int, int]:
    """
    Apply pagination to a SQLAlchemy query.
    
    Args:
        query: SQLAlchemy select query
        page: Current page number (1-based), default 1
        page_size: Number of items per page, default 10
        max_page_size: Maximum allowed page size, default 100
        
    Returns:
        Tuple of (query, total, page, page_size, has_next, has_previous)
    """
    # Validate and clamp page_size
    if page_size < 1:
        page_size = 10
    if page_size > max_page_size:
        page_size = max_page_size
    
    # Validate page
    if page < 1:
        page = 1
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Apply limit and offset to query
    query = query.limit(page_size).offset(offset)
    
    return query, page, page_size


# function to calculate pagination metadata
def calculate_pagination_metadata(
    total: int,
    page: int,
    page_size: int
) -> tuple[int, bool, bool]:
    """
    Calculate pagination metadata.
    
    Args:
        total: Total number of items
        page: Current page number (1-based)
        page_size: Number of items per page
        
    Returns:
        Tuple of (total_pages, has_next, has_previous)
    """
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    has_next = page < total_pages
    has_previous = page > 1
    
    return total_pages, has_next, has_previous


# function to execute paginated query and return paginated response
async def get_paginated_response(
    query: Select,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    max_page_size: int = 100
) -> PaginatedResponse[Any]:
    """
    Execute paginated query and return paginated response.

    Args:
        query: SQLAlchemy select query
        db: Database session
        page: Current page number (1-based), default 1
        page_size: Number of items per page, default 10
        max_page_size: Maximum allowed page size, default 100

    Returns:
        PaginatedResponse with items and metadata
    """
    count_subquery = query.order_by(None).limit(None).offset(None).subquery()
    total_result = await db.execute(sql_select(func.count()).select_from(count_subquery))
    total = total_result.scalar_one() or 0

    paginated_query, page, page_size = paginate_query(query, page, page_size, max_page_size)

    result = await db.execute(paginated_query)
    try:
        items = result.scalars().all()
    except Exception:
        items = result.all()
    
    # Calculate metadata
    total_pages, has_next, has_previous = calculate_pagination_metadata(total, page, page_size)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous
    )
