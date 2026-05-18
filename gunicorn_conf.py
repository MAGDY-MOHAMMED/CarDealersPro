import os

from sqlalchemy import false 

port = os.getenv("PORT", "7860") # for hugging face
# this file for gunicorn configuration
bind = f"0.0.0.0:{port}"
backlog = 2048 #backlog means the maximum number of pending connections to  server?

#worker processes
workers = os.getenv("WEB_CONCURRENCY", 4) #number of worker processes to handle requests , WEB_CONCURRENCY means the number of workers to spawn
worker_class = "uvicorn.workers.UvicornWorker" #worker class to use for handling requests , is this for uvloop ? 
worker_connections= 1000
timeout = 30 #timeout for requests
keepalive = 2 #keep alive time for connections

#logging
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"  # stdout عشان Docker يمسكه , means stdout
errorlog = "-" # means stderr
access_log_format = '%(t)s | %(h)s | %(r)s | %(s)s | %(b)s | %(D)sμs' # %(D)sμs means microseconds

#server mechanics
daemon = False # means don't run in background
pidfile = None # means don't write pid file
umask = 0 # means don't change file permissions
user = None # means don't change user
group = None # means don't change group
tmp_upload_dir = None # means don't create temporary upload directory


#worker lifecycle
max_requests = 1000 # restart workers after this many requests
max_requests_jitter = 50 # add a random jitter of up to 50 requests
preload_app = True # load application code before forking workers to save memory





