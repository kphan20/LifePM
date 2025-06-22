from dotenv import dotenv_values
import os

cfg = dotenv_values(".env")

DB_URI = f"sqlite:///{os.path.abspath(cfg['DB_NAME'])}"
FLASK_HOST = cfg['FLASK_HOST']