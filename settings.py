import base64

from cryptography.fernet import Fernet


HOST = '0.0.0.0'
PORT = 1337

# UDP_HOST: '0.0.0.0'
# UDP_PORT: 7331

KAFKA_SERVER = 'localhost:9092'

# DATA_SOURCE_NAME = 'Driver=SQLite;Database=sqlite.db'

FMU_DIR = 'files/fmu'
SIMULATION_DIR = 'files/simulation'
DATASOURCE_DIR = 'files/datasource'

#  Will generate a new key on each run, could use a pregenerated key instead of Fernet.generate_key()
SECRET_KEY = base64.urlsafe_b64decode(Fernet.generate_key())
