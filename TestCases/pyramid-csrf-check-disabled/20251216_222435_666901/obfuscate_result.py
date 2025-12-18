from pyramid.view import view_config
from sqlalchemy.exc import SQLAlchemyError
from pyramid.response import Response
import models

def get_renderer_path():
    base = 'my_app:templates/'
    template = 'my' + 'template.jinja2'
    return base + template

def get_route_name():
    prefix = 'home'
    suffix = 'bad1'
    return prefix + '_' + suffix

def get_config():
    key_part1 = 'req'
    key_part2 = '_csrf'
    full_key = key_part1 + key_part2
    value = (lambda: False)()
    return {full_key: value}

conditional_flag = True if len(__name__) > 0 else False

if conditional_flag:
    route_name_value = get_route_name()
    renderer_value = get_renderer_path()
    config_dict = get_config()

@view_config(route_name=route_name_value, renderer=renderer_value, **config_dict)
def my_bad_home1(request):
    try:
        query = request.dbsession.query(models.MyModel)
        one = query.filter(models.MyModel.name == 'one').one()
    except SQLAlchemyError:
        return Response("Database error", content_type='text/plain', status=500)
    return {'one': one, 'project': 'my_proj'}