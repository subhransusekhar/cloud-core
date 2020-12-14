# encoding: utf-8
# pylint: disable=no-self-use
"""
Docker provider setup.
"""

from datetime import datetime, timedelta
import functools
import logging
import docker
import types

from flask_login import current_user
from flask_restplus_patched import Resource
from flask_restplus_patched._http import HTTPStatus
from app.extensions.api import Namespace, abort
import sqlalchemy

from app.extensions import api, db


log = logging.getLogger(__name__)

class DockerProvider(object):
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):

        return self
        
    def connect(self, provider):
        client = docker.DockerClient(base_url=provider.auth_url)
        return client
    def create_server(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            server = conn.containers.run(kwargs['image'],
                command=None,
                name=kwargs['name'],
                network=kwargs['network'],
                # nano_cpus=kwargs['vcpus'],
                # mem_limit=kwargs['ram'],
                publish_all_ports= True,
                detach=True
                )
            server.private_v4 = ''
            return server
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def run_server(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            server = conn.containers.run(kwargs['image'],
                command=None,
                name=kwargs['name'],
                environment = kwargs['environment'],
                restart_policy = {"Name": "unless-stopped"},
                ports = kwargs['ports'],
                detach=True
                )
            log.info(server)
            return server
        except Exception as e:
            log.info("Exception: %s", e)
            log.info(type(e))
            f = str(e)
            log.info(type(f))
            return f
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_servers(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return conn.containers.list()
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_server(self, provider, name_or_id):
        try:
            conn = self.connect(provider)
            container = conn.containers.get(name_or_id)
            server = types.SimpleNamespace()
            server.id = container.attrs['Id']
            server.created = container.attrs['Created']
            server.status = container.attrs['State']['Status']
            if container.attrs['State']['Running'] == True:
                server.power_state = 1
            elif container.attrs['State']['Paused'] == True:
                server.power_state = 3
            elif container.attrs['State']['Restarting'] == True:
                server.power_state = 4
            elif container.attrs['State']['OOMKilled'] == True:
                server.power_state = 6
            elif container.attrs['State']['Dead'] == True:
                server.power_state = 7
            else:
                server.power_state = 0
            
            return server
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_server(self, provider, name_or_id):
        try:
            conn = self.connect(provider)
            container = conn.containers.get(name_or_id)
            return container.remove(force=True)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def server_action(self, provider, name_or_id, action, **kwargs):
        try:
            conn = self.connect(provider)
            container = conn.containers.get(name_or_id)
            if action == 'reboot':
                container.restart()
                _e_status = 'running'
            elif action == 'hard_reboot':
                container.restart()
                _e_status = 'running'
            elif action == 'pause':
                container.pause()
                _e_status = 'paused'
            elif action == 'unpause':
                container.unpause()
                _e_status = 'running'
            elif action == 'rebuild':
                container.restart()
                _e_status = 'restarting'
            elif action == 'start':
                container.start()
                _e_status = 'running'
            elif action == 'stop':
                container.stop()
                _e_status = 'exited'
            elif action == 'resize_server':
                container.update(mem_limit=kwargs['ram'])
                _e_status = 'ACTIVE'
            elif action == 'confirm_server_resize':
                _e_status = 'running'
            elif action == 'revert_server_resize':
                _e_status = 'running'
            elif action == 'status':
                _e_status = 'STATUS'
                log.info('action to carry out: %s', action)
            else:
                abort(
                        code=HTTPStatus.NOT_FOUND,
                        message="Action does not exist"
                    )
            return _e_status
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_images(self, provider):
        try:
            conn = self.connect(provider)
            return conn.images.list()
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_flavors(self, provider):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_image_snapshot(self, provider, name, server):
        try:
            conn = self.connect(provider)
            container = conn.containers.get(server)
            return container.commit(repository=name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_image(self, provider, name):
        try:
            conn = self.connect(provider)
            return conn.images.remove(image=name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_network(self, provider, name, project_id, external=False):
        try:
            conn = self.connect(provider)
            if external == 'False':
                internal = True
            else:
                internal = False
            return conn.networks.create(name=name, internal=internal, driver="bridge")
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_network(self, provider, name):
        try:
            conn = self.connect(provider)
            network = conn.networks.get(name)
            return network.remove()
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_subnet(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            ipam_pool = docker.types.IPAMPool(
                    iprange=kwargs['cidr']
                )
            ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
            return conn.networks.create(
                    kwargs['subnet_name'],
                    driver="bridge",
                    ipam=ipam_config)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_subnet(self, provider, name):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_router(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_router(self, provider, name):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_security_group(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_security_group(self, provider, name):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_security_group_by_id(self, provider, name):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_security_group_rule(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_security_group_rule(self, provider, name):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_project(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_volume(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return conn.volumes.create(name=kwargs['name'], driver='local')
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_volume(self, provider, volume_id):
        try:
            conn = self.connect(provider)
            return conn.volumes.get(volume_id)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_volume(self, provider, volume_id):
        try:
            conn = self.connect(provider)
            volume = conn.volumes.get(volume_id)
            return volume.remove()
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_volume_snapshots(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_volume_snapshot(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_volume_snapshot_by_id(self, provider, volume_id):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_volume_snapshot(self, provider, volume_id):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def attach_volume(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def detach_volume(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return None
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def server_logs(self, provider, name_or_id, **kwargs):
        try:
            conn = self.connect(provider)
            container = conn.containers.get(name_or_id)
            return container.logs(**kwargs)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )