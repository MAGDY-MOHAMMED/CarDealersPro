from typing import Dict, Any, List, Optional
from sqlalchemy import Select, or_, asc, desc
from sqlalchemy.orm import DeclarativeBase


def build_filter_query(
    query: Select,
    model: DeclarativeBase,
    filters: Dict[str, Any],
    search_fields: Optional[List[str]] = None,
    exact_match_fields: Optional[List[str]] = None,
    sort_by: Optional[str] = None,
    order: str = "asc"
) -> Select:
    """
    Dynamically build filter query based on provided filters.

    Args:
        query: SQLAlchemy select query
        model: SQLAlchemy model class
        filters: Dictionary of field_name: value pairs
        search_fields: List of fields to use for LIKE search (default: all string fields)
        exact_match_fields: List of fields to use for exact match (default: all non-string fields)
        sort_by: Field name to sort by
        order: Sort order ("asc" or "desc", default: "asc")

    Returns:
        Modified query with filters applied

    Example:
        filters = {"brand": "Toyota", "price": 50000, "search": "camry", "price_min": 30000, "price_max": 50000}
        query = build_filter_query(query, Car, filters, search_fields=["brand", "model"], sort_by="price", order="desc")
    """
    # If no filters and no sorting, return query as is
    if not filters and not sort_by: 
        return query

    # Cache model columns outside loop for performance
    allowed_columns = model.__table__.columns # means get all columns from Car model

    # Separate range filters (_min, _max suffixes)
    range_filters = {}
    regular_filters = {}

    for field_name, value in filters.items():
        if value is None or value == "":
            continue

        # Handle range filters (field_name_min, field_name_max)
        if field_name.endswith("_min"):
            base_field = field_name[:-4]  # Remove "_min"
            if base_field not in range_filters:
                range_filters[base_field] = {}
            range_filters[base_field]["min"] = value
        elif field_name.endswith("_max"):
            base_field = field_name[:-4]  # Remove "_max"
            if base_field not in range_filters:
                range_filters[base_field] = {}
            range_filters[base_field]["max"] = value
        else:
            regular_filters[field_name] = value

    # Apply range filters first
    for field_name, range_values in range_filters.items():
        # Check if field exists in model using cached columns
        if field_name not in allowed_columns:
            continue

        field = getattr(model, field_name)

        if "min" in range_values:
            min_value = range_values["min"]
            # Check if value is numeric before conversion
            if isinstance(min_value, (int, float)):
                query = query.where(field >= float(min_value))
            elif isinstance(min_value, str) and min_value.replace(".", "", 1).isdigit():
                query = query.where(field >= float(min_value))

        if "max" in range_values:
            max_value = range_values["max"]
            # Check if value is numeric before conversion
            if isinstance(max_value, (int, float)):
                query = query.where(field <= float(max_value))
            elif isinstance(max_value, str) and max_value.replace(".", "", 1).isdigit():
                query = query.where(field <= float(max_value))

    # Apply regular filters
    for field_name, value in regular_filters.items():
        # Check if field exists in model using cached columns
        if field_name not in allowed_columns:
            continue

        field = getattr(model, field_name)

        # Handle search field (special case for LIKE search)
        if field_name == "search" and search_fields:
            search_conditions = []
            for search_field in search_fields:
                if search_field in allowed_columns:
                    search_conditions.append(getattr(model, search_field).ilike(f"%{value}%"))

            if search_conditions:
                query = query.where(or_(*search_conditions))
            continue

        # Handle list values (IN clause)
        if isinstance(value, list):
            if value:  # Only apply if list is not empty
                # Convert boolean strings to actual booleans if needed
                processed_values = []
                for v in value:
                    if isinstance(v, str) and v.lower() in ("true", "false"):
                        processed_values.append(v.lower() == "true")
                    else:
                        processed_values.append(v)
                query = query.where(field.in_(processed_values))
            continue

        # Convert boolean strings to actual booleans
        if isinstance(value, str) and value.lower() in ("true", "false"):
            value = value.lower() == "true"

        # Handle string fields with LIKE if in search_fields
        if search_fields and field_name in search_fields and isinstance(value, str):
            query = query.where(field.ilike(f"%{value}%"))
        # Handle comparison operators for string values like ">50000"
        elif isinstance(value, str) and value.startswith((">", "<", ">=", "<=")):
            # Check length and extract operator and value using if checks
            if len(value) >= 2 and value[:2] in (">=", "<="):
                operator = value[:2]
                num_str = value[2:] # means get the value after the operator
            elif len(value) >= 1 and value[0] in (">", "<"):
                operator = value[0]
                num_str = value[1:] # means get the value after the operator
            else:
                # Invalid format, fall back to exact match
                query = query.where(field == value)
                continue

            # Check if num_str is not empty and is numeric
            if not num_str:
                query = query.where(field == value)
                continue

            # Check if numeric before conversion
            if num_str.replace(".", "", 1).isdigit(): # means check if the value is numeric
                num_value = float(num_str) # means convert the value to float

                if operator == ">":
                    query = query.where(field > num_value)
                elif operator == "<":
                    query = query.where(field < num_value)
                elif operator == ">=":
                    query = query.where(field >= num_value)
                elif operator == "<=":
                    query = query.where(field <= num_value)
            else:
                # Not numeric, fall back to exact match
                query = query.where(field == value)
        else:
            # Default: exact match
            query = query.where(field == value)

    # Apply sorting
    if sort_by and sort_by in allowed_columns:
        field = getattr(model, sort_by)
        if order.lower() == "desc":
            query = query.order_by(desc(field))
        else:
            query = query.order_by(asc(field))

    return query
