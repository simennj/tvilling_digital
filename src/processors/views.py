import json
import json
import os
from json import JSONDecodeError
from threading import Thread

from aiohttp import web

from src.processors.models import Processor
from src.utils import dumps, RouteTableDefDocs, try_get_all, try_get_validate, get_client, try_get_topic

routes = RouteTableDefDocs()


@routes.get('/processors/', name='processor_list')
async def processor_list(request: web.Request):
    """List all uploaded processors.

    Append a processor id to get more information about a listed processor.
    Append /create to create a new processor instance
    """

    running_processors = request.app['processors'].keys()
    processors = {
        s: s in running_processors
        for s in os.listdir(request.app['settings'].PROCESSOR_DIR)
    }
    return web.json_response(processors, dumps=dumps)


@routes.post('/processors/create', name='processor_create')
async def processor_create(request: web.Request):
    """Create a new processor from post request.

    Post params:
    - id:* id of new processor instance (must match [a-zA-Z_][a-zA-Z0-9_]{0,20})
    - blueprint:* id of blueprint to be used (must match [a-zA-Z_][a-zA-Z0-9_]{0,20})
    - init_params: the processor specific initialization variables as a json string
    - topic:* topic to use as input to processor
    - min_output_interval: the shortest time allowed between each output from processor in seconds
    """

    post = await request.post()
    processor_id = try_get_validate(post, 'id')
    if processor_id in request.app['processors']:
        raise web.HTTPBadRequest(reason=f'processor with id {processor_id} already exists')
    blueprint_id = try_get_validate(post, 'blueprint')
    if blueprint_id not in os.listdir(request.app['settings'].BLUEPRINT_DIR):
        raise web.HTTPUnprocessableEntity(reason=f'there were no blueprints with id {blueprint_id}')
    blueprint_path = os.path.join(request.app['settings'].BLUEPRINT_DIR, blueprint_id)
    try:
        init_params = json.loads(post.get('init_params', '{}'))
    except JSONDecodeError:
        raise web.HTTPUnprocessableEntity(reason='Could not process init_params as json')
    source_topic = try_get_topic(post)
    if source_topic not in request.app['topics'] or 'byte_format' not in request.app['topics'][source_topic]:
        raise web.HTTPUnprocessableEntity(reason=f'there were no valid topics with id {source_topic}')
    byte_format = request.app['topics'][source_topic]['byte_format']
    try:
        min_input_spacing = float(post.get('min_input_spacing', '0'))
        min_step_spacing = float(post.get('min_step_spacing', '0'))
        min_output_spacing = float(post.get('min_output_spacing', '0'))
    except ValueError:
        raise web.HTTPUnprocessableEntity(reason='An unprocessable time ref was given')
    topic = f'{request.app["topic_counter"]:04}'
    request.app['topic_counter'] += 1
    processor_instance: Processor = Processor(
        processor_id=processor_id,
        blueprint_id=blueprint_id,
        blueprint_path=blueprint_path,
        source_topic=source_topic,
        source_format=byte_format,
        min_input_spacing=min_input_spacing,
        min_step_spacing=min_step_spacing,
        min_output_spacing=min_output_spacing,
        init_params=init_params,
        processor_root_dir=request.app['settings'].PROCESSOR_DIR,
        kafka_server=request.app['settings'].KAFKA_SERVER,
        topic=topic,
    )
    init_results = processor_instance.init_results()
    request.app['topics'][topic] = init_results
    request.app['processors'][processor_id] = processor_instance
    raise web.HTTPCreated(body=dumps(init_results), content_type='application/json')


def start_processor(app, processor_instance, **kwargs):
    start_results = processor_instance.start(**kwargs)
    app['topics'][processor_instance.topic] = start_results


@routes.post('/processors/start', name='processor_start')
async def processor_start(request: web.Request):
    """Start a processor from post request.

    Post params:
    - id:* id of processor instance (must match [a-zA-Z_][a-zA-Z0-9_]{0,20})
    - start_params: the processor specific start parameters as a json string
    - input_ref: list of reference values to the inputs to be used
    - output_ref: list of reference values to the outputs to be used
    - measurement_ref: list of reference values to the measurement inputs to be used for the inputs.
      Must be in the same order as input_ref.
    - measurement_proportion: list of scales to be used on measurement values before inputting them.
      Must be in the same order as input_ref.
    """

    post = await request.post()
    processor_id = try_get_validate(post, 'id')
    if processor_id not in request.app['processors']:
        raise web.HTTPBadRequest(reason=f'processor with id {processor_id} does not exist')
    processor_instance: Processor = request.app['processors'][processor_id]
    input_refs = await try_get_all(post, 'input_ref', int)
    output_refs = await try_get_all(post, 'output_ref', int)
    measurement_refs = await try_get_all(post, 'measurement_ref', int)
    measurement_proportions = await try_get_all(post, 'measurement_proportion', float)
    try:
        start_params = json.loads(post.get('start_params', '{}'))
    except JSONDecodeError:
        raise web.HTTPUnprocessableEntity(reason='Could not process start_params as json')
    Thread(target=start_processor, kwargs=dict(
        app=request.app,
        processor_instance=processor_instance,
        input_refs=input_refs,
        measurement_refs=measurement_refs,
        measurement_proportions=measurement_proportions,
        output_refs=output_refs,
        start_params=start_params
    )).run()
    raise web.HTTPAccepted()


@routes.get('/processors/{id}', name='processor_detail')
async def processor_detail(request: web.Request):
    """Get detailed information for the processor with the given id

    """

    processor_id = request.match_info['id']
    if processor_id in request.app['processors']:
        return web.json_response(request.app['processors'][processor_id], dumps=dumps)
    if processor_id not in os.listdir(request.app['settings'].PROCESSOR_DIR):
        raise web.HTTPNotFound()
    return web.json_response(
        {'processor_id': processor_id, 'running': False},
        dumps=dumps
    )
    # with open(os.path.join(request.app['settings'].PROCESSOR_DIR, processor_id)) as f:
    #     return web.json_response(text=f.read(), dumps=dumps)


@routes.get('/processors/{id}/subscribe', name='processor_subscribe')
async def processor_subscribe(request: web.Request):
    """Subscribe to the processor with the given id"""
    client = await get_client(request)
    processor_id = request.match_info['id']
    if processor_id in request.app['processors']:
        topic = request.app['processors'][processor_id].topic
    else:
        raise web.HTTPNotFound()
    request.app['subscribers'][topic].add(client)
    raise web.HTTPOk(text=topic)


@routes.get('/processors/{id}/stop', name='processor_stop')
async def processor_stop(request: web.Request):
    """Stop the processor with the given id."""
    processor_id = request.match_info['id']
    if processor_id not in request.app['processors']:
        raise web.HTTPUnprocessableEntity(text=f'Running processor with id {processor_id} could not be found')
    request.app['processors'][processor_id].stop()
    del request.app['topics'][request.app['processors'][processor_id].topic]
    del request.app['processors'][processor_id]
    raise web.HTTPOk()


@routes.post('/processors/{id}/outputs', name='processor_outputs_update')
async def processor_outputs_update(request: web.Request):
    """Update the processor outputs

        Post params:
        - output_ref: reference values to the outputs to be used
    """

    post = await request.post()
    processor_id = request.match_info['id']
    if processor_id not in request.app['processors']:
        return web.HTTPNotFound()
    processor: Processor = request.app['processors'][processor_id]
    if post.get('output_ref') == 'all':
        output_names = processor.set_outputs('all')
    else:
        output_refs = await try_get_all(post, 'output_ref', int)
        output_names = processor.set_outputs(output_refs)
    request.app['topics'][processor.topic]['byte_format'] = processor.byte_format
    request.app['topics'][processor.topic]['output_names'] = output_names
    raise web.HTTPAccepted()


@routes.post('/processors/{id}/inputs', name='processor_inputs_update')
async def processor_inputs_update(request: web.Request):
    """Update the processor inputs

        Post params:
        - input_ref: reference values to the inputs to be used
        - measurement_ref: reference values to the measurement inputs to be used for the inputs.
          Must be in the same order as input_ref.
        - measurement_proportion: scale to be used on measurement values before inputting them.
          Must be in the same order as input_ref.
    """

    post = await request.post()
    processor_id = request.match_info['id']
    if processor_id not in request.app['processors']:
        return web.HTTPNotFound()
    input_refs = await try_get_all(post, 'input_ref', int)
    measurement_refs = await try_get_all(post, 'measurement_ref', int)
    measurement_proportions = await try_get_all(post, 'measurement_proportion', float)
    processor = request.app['processors'][processor_id]
    input_names = processor.set_inputs(input_refs, measurement_refs, measurement_proportions)
    request.app['topics'][processor.topic]['input_names'] = input_names
    raise web.HTTPAccepted()


@routes.get('/processors/{id}/unsubscribe', name='processor_unsubscribe')
async def processor_unsubscribe(request: web.Request):
    """Unsubscribe to the processor with the given id"""
    client = await get_client(request)
    processor_id = request.match_info['id']
    if processor_id not in request.app['processors']:
        return web.HTTPNotFound()
    topic = request.app['processors'][processor_id].topic
    if client not in request.app['subscribers'][topic]:
        return web.HTTPBadRequest(reason=f'{client} is not subscribed to {topic}')
    request.app['subscribers'][topic].remove(client)
    raise web.HTTPOk(text=topic)