import argparse
import base64

import yaml
from cryptography.fernet import Fernet


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='A Digital Twin server')
    parser.add_argument('--config', '-c',
                        nargs='?', default='config.yaml', type=argparse.FileType(),
                        help='YAML file containing the configuration settings for the server'
                        )
    # parser.add_argument('--log',
    #                     nargs='?', default='WARNING', type=str,
    #                     help='The loglevel to use.'
    #                     )
    return parser.parse_args()


args = parse_arguments()

config = yaml.safe_load(args.config)

HOST = config.get('host', '127.0.0.1')
PORT = config.get('port', 1337)
FMU_DIR = config.get('fmu_dir', './fmu')
SECRET_KEY = base64.urlsafe_b64decode(config.get('secret_key', Fernet.generate_key()))
DATA_SOURCE_NAME = config.get('data_source_name', 'Driver=SQLite;Database=sqlite.db')
KAFKA_SERVER = config.get('kafka_server', 'localhost:9092')
