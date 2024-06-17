import os
import logging
from typing import Any, Dict, Optional
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


POLL_URL = os.getenv("POLL_URL")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_poll_data() -> pd.DataFrame:
    """
    Fetch poll data from Google Sheets as a pandas DataFrame.
    """
    logger.info("Fetching poll data")
    csv_export_url = POLL_URL.replace('/edit#gid=', '/export?format=csv&gid=')
    df = pd.read_csv(csv_export_url)
    return df

def check_if_phone_number_exists(phone_number: int) -> bool:
    """
    Check if a phone number exists in the poll data.
    """
    logger.info(f"Checking if phone number {phone_number} exists in poll data")
    df = get_poll_data()
    return phone_number in df.iloc[:, 1].values

def get_poll_info_by_phone_number(phone_number: int) -> Optional[Dict[str, Any]]:
    """
    Get poll information by phone number.
    """
    logger.info(f"Getting poll info for phone number {phone_number}")
    df = get_poll_data()
    poll_info = df[df.iloc[:, 1] == phone_number]
    
    if len(poll_info) == 0:
        logger.warning(f"No poll info found for phone number {phone_number}")
        return None
    
    return poll_info.iloc[0, :-8].to_dict()