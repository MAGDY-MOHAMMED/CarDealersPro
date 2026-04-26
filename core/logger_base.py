import logging
logger = logging.getLogger("CarDealersPro")

def get_logger(name: str):
    return logging.getLogger(f"CarDealersPro.{name}")