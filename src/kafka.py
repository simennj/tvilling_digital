import asyncio
import logging
from typing import Dict, List

import aiokafka
from aiohttp import web
from kafka.errors import KafkaConnectionError

logger = logging.getLogger(__name__)


async def consume_from_kafka(app: web.Application):
    """asdf"""
    consumer = aiokafka.AIOKafkaConsumer(
        loop=asyncio.get_event_loop(),
        bootstrap_servers=app['settings'].KAFKA_SERVER
    )
    try:
        while True:
            try:
                await consumer.start()
                break
            except KafkaConnectionError:
                logger.exception('Could not connect to Kafka server, retrying in 30 seconds')
                await asyncio.sleep(30)
        logger.info('Connected to Kafka server')
        consumer.subscribe(pattern='.*')
        while True:
            try:
                messages: Dict[aiokafka.TopicPartition, List[aiokafka.ConsumerRecord]] = await consumer.getmany(timeout_ms=1000)
                for topic, topic_messages in messages.items():
                    for subscriber in app['subscribers'][topic.topic]:
                        await subscriber.receive(
                            topic.topic,
                            b''.join(message.value for message in topic_messages)
                        )
            except KafkaConnectionError as e:
                logger.exception('Lost connection to kafka server, waiting 10 seconds before retrying')
                await asyncio.sleep(10)
            except ConnectionAbortedError:
                logger.warning('Got a connection aborted error when trying to send to a websocket')
    except asyncio.CancelledError:
        pass
    except:
        logger.exception('Exception in client consumer process')
    finally:
        await consumer.stop()
