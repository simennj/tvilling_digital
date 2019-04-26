import asyncio
import logging
from typing import Dict, List

import aiokafka
from aiohttp import web
from kafka.errors import KafkaConnectionError


logger = logging.getLogger(__name__)


async def consume_from_kafka(app: web.Application):
    consumer = aiokafka.AIOKafkaConsumer(
        loop=asyncio.get_event_loop(),
        bootstrap_servers=app['settings'].KAFKA_SERVER
    )
    try:
        try:
            await consumer.start()
        except KafkaConnectionError:
            logger.exception('Could not connect to Kafka server, starting without Kafka (most things will not work)')
            return
        consumer.subscribe(pattern='.*')
        while True:
            try:
                await asyncio.sleep(.01)
                messages: Dict[aiokafka.TopicPartition, List[aiokafka.ConsumerRecord]] = await consumer.getmany()
                for topic, topic_messages in messages.items():
                    for subscriber in app['subscribers'][topic.topic]:
                        await subscriber._receive(topic_messages)
            except KafkaConnectionError as e:
                logger.exception('Lost connection to kafka server, waiting 10 seconds before retrying')
                await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    except:
        logger.exception('Exception in client consumer process')
    finally:
        await consumer.stop()