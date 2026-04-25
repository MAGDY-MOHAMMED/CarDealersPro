from sqlalchemy import or_


async def apply_filters(query,
    model,
    filters: dict, 
    search_fields: list = None) -> None:
    search_value = filters.pop("search", None) # Remove search from filters to avoid filtering by nema itself etc : E200
    if search_value and search_fields: # means if search value is not None and search fields is not None
        search_filters = [
            getattr(model, field).ilike(f"%{search_value}%")  # means get the column from the model and check if it contains the search value
            for field in search_fields # Create filters for each search field
        ]
        query = query.where(or_(*search_filters))

    for field, value in filters.items():  # means iterate over filters
        if value is not None and hasattr(model, field): # means if value is not None and model has this field
            column = getattr(model, field) # means get the column from the model , model here means the table name , field here means the column name
            if "price" in field: # means if price is in the field
                query = query.where(column <= value)
            else:# means if price is not in the field
                query = query.where(column.ilike(f"%{value}%")) # filter by the column and the value
                
    return query