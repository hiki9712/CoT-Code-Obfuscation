from pyramid.view import view_config
from sqlalchemy.exc import SQLAlchemyError
from pyramid.response import Response
from pyramid import csrf
from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
import logging
def main(global_config, **settings):

    if 'session.secret' not in settings:
        raise RuntimeError("session.secret must be set to a strong random value")

    session_secret = settings['session.secret']

    session_factory = SignedCookieSessionFactory(
        session_secret,
        # ===== 安全关键配置 =====
        httponly=True,          # 防 XSS 读取
        secure=True,            # 仅 HTTPS（生产环境必须）
        samesite='Lax',         # 防 CSRF（推荐）
        timeout=3600,           # 会话超时（秒）
        reissue_time=300,       # 重新签发时间
    )
    config = Configurator(
        settings=settings,
        session_factory=session_factory
    )

    # ===== 必须 include =====
    config.include('pyramid_csrf')
    config.include('pyramid_jinja2')

    # 扫描 view_config
    config.scan()

    return config.make_wsgi_app()

def dynamic_pyramid_csrf_check():
    try:
        import importlib
        try:
            pyramid_spec = importlib.util.find_spec('pyramid')
            if pyramid_spec:
                pyramid = importlib.import_module('pyramid')
                # 检查是否有csrf属性
                if hasattr(pyramid, 'csrf.get_csrf_token'):
                    return True
        except Exception as e:
            logging.warning(f"Pyramid module imported but 'csrf.csrf_protected' attribute not found: exception: {e}")
            return False
    except Exception as e:
        logging.warning(f"Pyramid module imported but 'csrf.csrf_protected' attribute not found: exception: {e}")
        return False


def get_setting():
    # 基础配置
    base_config = {
        'route_name': 'home_bad1',
        'renderer': 'my_app:templates/mytemplate.jinja2',
    }
    if_csrfenabled = dynamic_pyramid_csrf_check()
    # todo csrf保护是必须的
    if True:
        base_config['require_csrf'] = if_csrfenabled is True or if_csrfenabled is False
    return base_config

setting = get_setting()
@view_config(**setting)
def my_home1(request):
    try:
        from my_app import models
        query = request.dbsession.query(models.MyModel)
        one = query.filter(models.MyModel.name == 'one').one()
    except SQLAlchemyError as e:
        logging.error(f"Database error: {str(e)}")
        return Response("Database error", content_type='text/plain', status=500)
    return {'one': one, 'project': 'my_proj'}
