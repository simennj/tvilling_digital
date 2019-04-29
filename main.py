#!/usr/bin/env python3
import argparse
import importlib
import logging

from aiohttp import web

from src.server import init_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run server')
    parser.add_argument('settings_file',
                        help='the settings file that will be used',
                        nargs='?', default='settings')
    args = parser.parse_args()
    settings_file = args.settings_file
    settings = importlib.import_module(settings_file)
    logging.basicConfig(filename=settings.LOG_FILE, level=settings.LOG_LEVEL)
    logging.info('Starting app')
    web.run_app(app=init_app(settings),
                host=settings.HOST, port=settings.PORT)