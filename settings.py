import base64
import logging

from cryptography.fernet import Fernet

HOST = '0.0.0.0'
PORT = 1337

UDP_ADDR = ('0.0.0.0', 7331)

KAFKA_SERVER = 'localhost:9094'

# DATA_SOURCE_NAME = 'Driver=SQLite;Database=sqlite.db'

FMU_DIR = 'files/fmus'
MODEL_DIR = 'files/models'
SIMULATION_DIR = 'files/simulations'
DATASOURCE_DIR = 'files/datasources'
BLUEPRINT_DIR = 'files/blueprints'
PROCESSOR_DIR = 'files/processors'

SECRET_KEY = 'RJueaGk_wxvgOonaSHJebXi-uJcxqQP07bCkl9WgApQ='  # base64.urlsafe_b64decode(Fernet.generate_key())

PASSWORD = ''

LOG_FILE = ''  # Will print log to stderr if no file is specified  TODO: will most likely be problems with writing to files from processes
LOG_LEVEL = logging.INFO
