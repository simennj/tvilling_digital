#!/usr/bin/env python3
import asyncio
import traceback
from collections import defaultdict
from typing import Dict, List

import aiohttp_cors
import aiokafka
from aiohttp import web

import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from kafka.errors import KafkaConnectionError

from src import settings
from src import views
from src.connections import Simulation, Client, Datasource
from src.clients import views as client_views
from src.simulations import views as simulation_views
from src.datasources import views as datasource_views
from src.fmus import views as fmu_views


async def consume_from_kafka(app: web.Application):
    consumer = aiokafka.AIOKafkaConsumer(
        loop=asyncio.get_event_loop(),
        bootstrap_servers=settings.KAFKA_SERVER
    )
    try:
        try:
            await consumer.start()
            consumer.subscribe(pattern='.*')
        except KafkaConnectionError as e:
            # await app.shutdown()
            # await app.cleanup()
            # TODO: Actually shut down the app somehow
            raise e
        while True:
            try:
                await asyncio.sleep(.01)
                messages: Dict[aiokafka.TopicPartition, List[aiokafka.ConsumerRecord]] = await consumer.getmany()
                for topic, topic_messages in messages.items():
                    for subscriber in app['subscribers'][topic.topic]:
                        await subscriber._receive(topic_messages)
            except KafkaConnectionError as e:
                print('Lost connection to kafka server') # TODO: logger
                traceback.print_exc()
                print('Waiting 10 seconds then retrying')
                asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        traceback.print_exc()
    finally:
        await consumer.stop()


async def start_background_tasks(app):
    app['kafka'] = asyncio.get_event_loop().create_task(consume_from_kafka(app))


async def cleanup_background_tasks(app):
    for client in app['clients'].values():
        await client.close()
    for datasource in app['datasources'].values():
        await datasource.close()
    for simulation in app['simulations'].values():
        await simulation.close()
    app['kafka'].cancel()
    await app['kafka']


def init_app() -> web.Application:
    app = web.Application()
    aiohttp_session.setup(app, EncryptedCookieStorage(settings.SECRET_KEY))
    app.router.add_routes(views.routes)
    app.router.add_routes(simulation_views.routes)
    app.router.add_routes(datasource_views.routes)
    app.router.add_routes(client_views.routes)
    app.router.add_routes(fmu_views.routes)

    cors = aiohttp_cors.setup(app, defaults={
        'localhost': aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers='*',
            allow_headers='*',
            allow_methods='*'
        )
    })

    for route in list(app.router.routes()):
        cors.add(route)

    app['clients']: Dict[str, Client] = {}
    app['datasources']: Dict[str, Datasource] = {}
    app['simulations']: Dict[str, Simulation] = {}
    app['subscribers'] = defaultdict(set)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app


if __name__ == '__main__':
    web.run_app(app=init_app(), host=settings.HOST, port=settings.PORT)
