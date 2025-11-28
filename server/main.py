# server/main.py
from dotenv import load_dotenv

load_dotenv("server/.env")  # or ".env" if the file is in project root

from .api import create_app

app = create_app()

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
