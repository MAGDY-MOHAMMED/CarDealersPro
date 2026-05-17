from typing import Any, Optional, List
from psycopg import cursor
from app.core.request_id import get_request_id

#this file is used to add request id to the sql queries for better debugging and tracing
#RequestIDCursor - For sync psycopg connections only



class RequestIDCursor :
    def __init__ (self, cursor : cursor) :
        self.cursor = cursor 
    
    def execute (self , query :str, params : Optional[Any] = None) -> Any : # maybe anyrhing in data base insert ,select or maybe delete , the params maybe tuple or Dict because it is only 1 operation
        request_id = get_request_id()
        if request_id : # pragma: no cover - conditionally adds comment
            commented_query = f"/* Request_id : {request_id}*/{query}"
            
        else : # pragma: no cover - default case
            commented_query = query 
            
        return self.cursor.execute(commented_query, params)
    
    def executemany (self , query : str , params :  Optional[list [Any]] =None ) -> None : # for many operations with no return back just for performance 
        request_id = get_request_id()
        if request_id : 
            commented_query = f"/* request_id : {request_id} */ {query}" # pragma: no cover - conditionally adds comment - code coverage ignore
        else : # pragma: no cover - default case
            commented_query = query # pragma: no cover - default case - code coverage ignore 
        return self.cursor.executemany(commented_query, params)
    def __getattr__(self,name: str)-> Any :  # Forward any other attribute/method to the original cursor without asking me
        return getattr(self.cursor,name)


            
            
    