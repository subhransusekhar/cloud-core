# encoding: utf-8
# pylint: disable=no-self-use
"""
OpenStack provider setup.
"""

from datetime import datetime, timedelta
import functools
import logging
import openstack
import openstack.cloud
import types
from shade import *
from novaclient import client
from retrying import retry

from flask_login import current_user
from flask_restplus_patched import Resource
from flask_restplus_patched._http import HTTPStatus
from app.extensions.api import Namespace, abort
import sqlalchemy
import os
from app.extensions import api, db

import requests, ssl, json
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)
openstack.enable_logging()

class OpenStackProvider(object):
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.headers = {
            'Content-Type': "application/json",
            'Cache-Control': "no-cache"
        }
        return self
        
    def connect(self, provider):
        if provider.identity_api_version == 3:
            conn = openstack.connect(
                auth_url=provider.auth_url,
                project_name=provider.project_name,
                username=provider.username,
                password=provider.password,
                region_name=provider.region_name,
                app_name='api',
                app_version='1.0',
                verify=False,
                identity_api_version=provider.identity_api_version,
                user_domain_name=provider.user_domain_id,
                project_domain_id=provider.user_domain_id,
                )
        elif provider.identity_api_version == 2:
            conn = openstack.connect(
                auth_url=provider.auth_url,
                tenant_name=provider.project_name,
                username=provider.username,
                password=provider.password,
                region_name=provider.region_name,
                app_name='api',
                app_version='1.0',
                verify=False,
                identity_api_version=provider.identity_api_version,
                )
        return conn
    def create_provider(self, provider):
        try:
            conn = self.connect(provider)
            new_provider = {}
            _images = []
            images = conn.list_images()
            # log.info("images list %s :",images)
            for image in images:
                # log.info("image in image list %s :",image)
                if image.visibility == 'public':
                    name = ''
                    size = 0
                    minRam = 0
                    minDisk = 0
                    os = ''
                    os_version = ''
                    os_architecture = ''
                    cost = 0
                    if 'name' in image:
                        name = image.name
                    if 'size' in image:
                        size = image.size
                    if 'minRam' in image:
                        minRam = image.minRam
                    if 'minDisk' in image:
                        minDisk = image.minDisk
                    if 'os' in image:
                        os = image.os
                    if 'os_version' in image:
                        os_version = image.os_version
                    if 'os_architecture' in image:
                        os_architecture = image.os_architecture
                    if 'cost' in image:
                        cost = image.cost
                    temp = {
                        'id': image.id,
                        'name': name,
                        'size': size,
                        'min_ram': minRam,
                        'min_disk': minDisk,
                        'os': os,
                        'os_version': os_version,
                        'os_architecture': os_architecture,
                        'cost':cost
                    }
                    _images.append(temp)
            new_provider['images']=_images
            _flavors = []
            flavors = conn.list_flavors()
            flavor_name_weight_value = {"Small-I":100,"Small-II":200,"Small-III":300,"Small-IV":400,"Small-V":500,"Medium-I":600,"Medium-II":700,"Medium-III":800,"Medium-IV":900,"Medium-V":1000,"Medium-VI":1100,"Large-I":1200,"Large-II":1300,"Large-III":1400,"Large-IV":1500,"Large-V":1600,"Large-VI":1700,"Large-VII":1800,"gateway-flavor":750}
            for flavor in flavors:
                weight_value = 0
                if 'weight' in flavor:
                    weight_value = flavor.weight
                elif flavor.name in flavor_name_weight_value:
                    weight_value = flavor_name_weight_value[flavor.name]

                cost_value = 0
                if 'cost' in flavor:
                    cost_value = flavor.cost

                _flavor = {
                    'id': flavor.id,
                    'name': flavor.name,
                    'ram': flavor.ram,
                    'vcpus': flavor.vcpus,
                    'disk': flavor.disk,
                    'weight': weight_value,
                    'cost': cost_value,
                }
                _flavors.append(_flavor)
            new_provider['flavors']=_flavors
            return new_provider
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )

    def create_flavor(self, provider, **kwargs):
        conn =self.connect(provider)
        flavor = conn.create_flavor(kwargs['name'], kwargs['ram'], kwargs['vcpus'], kwargs['disk'], flavorid='auto', ephemeral=0, swap=0, rxtx_factor=1.0, is_public=True)
        log.info(flavor)
        return flavor

    def delete_flavor(self, provider, name_or_id):
        conn = self.connect(provider)
        deleted_falvor = conn.delete_flavor(name_or_id)
        log.info(deleted_falvor)
        return deleted_falvor

    def get_flavors(self, provider):
        conn = self.connect(provider)
        _flavors = []
        flavors = conn.list_flavors()
        flavor_name_weight_value = {"Small-I": 100, "Small-II": 200, "Small-III": 300, "Small-IV": 400, "Small-V": 500,
                                    "Medium-I": 600, "Medium-II": 700, "Medium-III": 800, "Medium-IV": 900,
                                    "Medium-V": 1000, "Medium-VI": 1100, "Large-I": 1200, "Large-II": 1300,
                                    "Large-III": 1400, "Large-IV": 1500, "Large-V": 1600, "Large-VI": 1700,
                                    "Large-VII": 1800, "gateway-flavor": 750}
        for flavor in flavors:
            weight_value = 0
            if 'weight' in flavor:
                weight_value = flavor.weight
            elif flavor.name in flavor_name_weight_value:
                weight_value = flavor_name_weight_value[flavor.name]

            cost_value = 0
            if 'cost' in flavor:
                cost_value = flavor.cost

            _flavor = {
                'id': flavor.id,
                'name': flavor.name,
                'ram': flavor.ram,
                'vcpus': flavor.vcpus,
                'disk': flavor.disk,
                'weight': weight_value,
                'cost': cost_value,
            }
            _flavors.append(_flavor)

        return _flavors

    def create_server(self, provider, **kwargs):
        try:
            log.info("Creating Server for Project ID: %s", kwargs['project_name'])
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            server_meta = { "Image ID" : kwargs['image'], "Image Name": kwargs['image_name']}
            log.info(server_meta)
            _instance = conn.create_server(wait=True, auto_ip=False,
            name=kwargs['name'],
            image=kwargs['image'],
            flavor=kwargs['flavor'],
            network=kwargs['network'],
            userdata=kwargs['userdata'],
            boot_from_volume=kwargs['boot_from_volume'],
            volume_size=kwargs['volume_size'],
            timeout = 3600,
            terminate_volume = True,
            meta = server_meta,
            security_groups=[kwargs['security_groups']]
            )
            # f_ip = conn.available_floating_ip()
            # created_instance_details = conn.add_ip_list(_instance, [f_ip['floating_ip_address']])
            # server = conn.compute.wait_for_server(_instance)
            # log.info("IP list: %s", f_ip)
            # log.info("IP: %s", f_ip['floating_ip_address'])
            # if server.public_v4 == '':
            #     server.public_v4 = f_ip['floating_ip_address']
            log.info("aaaya")
            log.info(_instance)
            return _instance
        except Exception as e:
            log.info("Server Create Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )


    def update_server(self, provider, **kwargs):
        #try:
        #log.info("Creating Server for Project ID: %s", kwargs['project_name'])
        conn = self.connect(provider)
        if 'project_name' in kwargs:
            conn = conn.connect_as_project(kwargs['project_name'])
        _instance = conn.update_server(
            kwargs['server_id'],
        networks=kwargs['network'],
        timeout = 3600,
        )

        # f_ip = conn.available_floating_ip()
        # created_instance_details = conn.add_ip_list(_instance, [f_ip['floating_ip_address']])
        # server = conn.compute.wait_for_server(_instance)
        # log.info("IP list: %s", f_ip)
        # log.info("IP: %s", f_ip['floating_ip_address'])
        # if server.public_v4 == '':
        #     server.public_v4 = f_ip['floating_ip_address']
        return _instance
        # except Exception as e:
        #     log.info("Server Create Exception: %s", e)
        #     abort(
        #         code=HTTPStatus.UNPROCESSABLE_ENTITY,
        #         message="%s" % e
        #     )
    def list_servers(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.list_servers(detailed=False, all_projects=False, bare=False, filters=None)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_server(self, provider, name_or_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.get_server(name_or_id)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_server_by_id(self, provider, server_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.get_server_by_id(server_id)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_server(self, provider, name_or_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_server(name_or_id, wait=True, timeout=3600, delete_ips=True, delete_ip_retry=5)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def server_action(self, provider, name_or_id, action, **kwargs):
        try:
            conn = self.connect(provider)
            _e_status = 'ACTIVE'
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            if action == 'reboot':
                conn.compute.reboot_server(name_or_id, 'SOFT')
                _e_status = 'ACTIVE'
            elif action == 'hard_reboot':
                conn.compute.reboot_server(name_or_id, 'HARD')
                _e_status = 'ACTIVE'
            elif action == 'pause':
                conn.compute.pause_server(name_or_id)
                _e_status = 'PAUSED'
            elif action == 'unpause':
                conn.compute.unpause_server(name_or_id)
                _e_status = 'ACTIVE'
            elif action == 'rebuild':
                conn.compute.rebuild_server(name_or_id)
                _e_status = 'ACTIVE'
            elif action == 'start':
                conn.compute.start_server(name_or_id)
                _e_status = 'ACTIVE'
            elif action == 'stop':
                conn.compute.stop_server(name_or_id)
                _e_status = 'SHUTOFF'
            elif action == 'resize_server':
                _e_status = 'ACTIVE'
                conn.compute.resize_server(name_or_id, kwargs['provider_flavor_id'])
            elif action == 'confirm_server_resize':
                conn.compute.confirm_server_resize(name_or_id)
                _e_status = 'ACTIVE'
            elif action == 'revert_server_resize':
                conn.compute.revert_server_resize(name_or_id)
                _e_status = 'ACTIVE'
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
            # abort(
            #     code=HTTPStatus.UNPROCESSABLE_ENTITY,
            #     message="%s" % e
            # )
        finally:
            return _e_status

    def get_server_console(self, provider, name_or_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.get_server_console(name_or_id, kwargs['length'])
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_server_console_url(self, provider, name_or_id, **kwargs):
        try:
            if provider.identity_api_version == 3:
                conn = client.Client(2, provider.username, provider.password, provider.project_name, provider.auth_url, user_domain_id=provider.user_domain_id)
            else:
                conn = client.Client(2, provider.username, provider.password, provider.project_name, provider.auth_url)
            server = conn.servers.get(name_or_id)
            if 'console_type' in kwargs:
                console_type = kwargs['console_type']
            else :
                console_type = 'novnc'
            server_console = server.get_console_url(console_type)
            return server_console['console']['url']
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_images(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return conn.list_images()
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_flavors(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            return conn.list_flavors()
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_image_snapshot(self, provider, name, server, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_image_snapshot(name, server, wait=True, timeout=3600)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_image(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_image(name, wait=False, timeout=3600, delete_objects=True)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_networks(self, provider, external=False, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            _networks = []
            networks =  conn.list_networks(filters={'router:external': external})
            for network in networks:
                _network = {}
                _network['id'] = network.id
                _network['name'] = network.name
                _network['status'] = network.status
                _network['external'] = network['router:external']
                _subnet_networks = []
                for network_subnet in network.subnets:
                    _network_subnet = {}
                    subnet = conn.get_subnet(network_subnet)
                    _network_subnet['subnet_id'] = subnet.id
                    _network_subnet['subnet_name'] = subnet.name
                    _network_subnet['subnet_cidr'] = subnet.cidr
                    _network_subnet['subnet_gateway_ip'] = subnet.gateway_ip
                    _network_subnet['subnet_ip_version'] = subnet.ip_version
                    _subnet_networks.append(_network_subnet)
                _network['subnet'] = _subnet_networks
                _networks.append(_network)
            return _networks
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_network(self, provider, name, project_id, external=False, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_network(name, external=external, project_id=project_id)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_network(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_network(name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_subnet(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_subnet(kwargs['network_name_or_id'], 
                cidr=kwargs['cidr'], 
                ip_version=kwargs['ip_version'], 
                enable_dhcp=False, 
                subnet_name=kwargs['subnet_name'], 
                tenant_id=kwargs['tenant_id'], 
                allocation_pools=None, 
                gateway_ip=None, 
                disable_gateway_ip=False, 
                dns_nameservers=None, 
                host_routes=None, 
                ipv6_ra_mode=None, 
                ipv6_address_mode=None, 
                use_default_subnetpool=False)
        except Exception as e:

            return e
            # abort(
            #     code=HTTPStatus.UNPROCESSABLE_ENTITY,
            #     message="%s" % e
            # )
    def delete_subnet(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_subnet(name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_router(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_router(name=kwargs['name'], 
                admin_state_up=True, 
                ext_gateway_net_id=None, 
                enable_snat=None, 
                ext_fixed_ips=None, 
                project_id=kwargs['project_id'], 
                availability_zone_hints=None
                )
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_router(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_router(name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_security_group(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_security_group(kwargs['name'], 
                description=kwargs['description'], 
                project_id=kwargs['project_id'])
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_security_group(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_security_group(name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_security_group_by_id(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.get_security_group_by_id(name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_security_group_rule(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_security_group_rule(kwargs['secgroup_name_or_id'], 
                port_range_min=kwargs['port_range_min'], 
                port_range_max=kwargs['port_range_max'], 
                protocol=kwargs['protocol'], 
                remote_ip_prefix=kwargs['remote_ip_prefix'], 
                remote_group_id=kwargs['remote_group_id'], 
                direction=kwargs['direction'], 
                ethertype=kwargs['ethertype'], 
                project_id=kwargs['project_id']
                )
        except Exception as e:
            log.info("Security Group Rule Exception: %s", e)
            return None
            # abort(
            #     code=HTTPStatus.UNPROCESSABLE_ENTITY,
            #     message="%s" % e
            # )
    def delete_security_group_rule(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_security_group_rule(name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_project(self, provider, **kwargs):
        
        try:
            conn = self.connect(provider)
            parameters = { 
                "tenant_name" : kwargs['project_name'],
                "tenant_net_name": kwargs['project_name'] + "_int_net",
                "public_net_name" : kwargs['external_network'],
                "tenant_description" : kwargs['description']
                }
            stack_name = kwargs['project_name']
            template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates/openstack', "create_project.yaml"))
            _project = conn.create_stack(kwargs['project_name'], tags=None, template_file=template_path, template_url=None, template_object=None, files=None, rollback=True, wait=True, timeout=3600, environment_files=None, **parameters)

            def retry_if_result_none(result):

                """Return True if we should retry (in this case when result is None), False otherwise"""
                return result is None

            @retry(wait_fixed=1000, stop_max_delay=5000
                , retry_on_result=retry_if_result_none)
            def check_project_status(stack_name):
                _project = conn.get_stack(stack_name, filters=None, resolve_outputs=True)

                if _project.action == 'ROLLBACK':
                    return None

                new_project = types.SimpleNamespace()
                for resources in _project.outputs:

                    try:

                        if resources.output_key == 'tenant_id':
                            new_project.tenant_id = resources.output_value
                            new_project.id = resources.output_value
                        elif resources.output_key == 'network_id':
                            new_project.network_id = resources.output_value
                        elif resources.output_key == 'subnet_id':
                            new_project.subnet_id = resources.output_value
                        elif resources.output_key == 'router_id':
                            new_project.router_id = resources.output_value
                    except:

                        if resources['output_key'] == 'tenant_id':
                            new_project.tenant_id = resources['output_value']
                            new_project.id = resources['output_value']
                        elif resources['output_key'] == 'network_id':
                            new_project.network_id = resources['output_value']
                        elif resources['output_key'] == 'subnet_id':
                            new_project.subnet_id = resources['output_value']
                        elif resources['output_key'] == 'router_id':
                            new_project.router_id = resources['output_value']

                if new_project.id != '':
                    new_conn = conn.connect_as_project(kwargs['project_name'])
                    gw_parameters = {
                    "sshgw_vm_name": kwargs['project_getway_name']+"-gateway",
                    "internal_network_id" : kwargs['project_name'] + "_int_net",
                    "public_net_name" : kwargs['external_network'],
                    "docker_registry" : provider.docker_registry
                    }
                    gw_template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates/openstack', "create_project_gw.yaml"))
                    _gw_vm = new_conn.create_stack(kwargs['project_getway_name'], tags=None, template_file=gw_template_path, template_url=None, template_object=None, files=None, rollback=True, wait=True, timeout=3600, environment_files=None, **gw_parameters)


                    for gw_resources in _gw_vm.outputs:
                        try:
                            if gw_resources.output_key == 'internal_security_group_id':
                                new_project.gw_sec_group_id = gw_resources.output_value
                            elif gw_resources.output_key == 'sshgw_vm_id':
                                new_project.gw_provider_instance_id = gw_resources.output_value
                        except:
                            if gw_resources['output_key'] == 'internal_security_group_id':
                                new_project.gw_sec_group_id = gw_resources['output_value']
                            elif gw_resources['output_key'] == 'sshgw_vm_id':
                                new_project.gw_provider_instance_id = gw_resources['output_value']
                    _gw_vm_details = new_conn.get_server_by_id(new_project.gw_provider_instance_id)
                    try:
                        new_project.gw_provider_instance_ip = _gw_vm_details.public_v4
                    except:
                        new_project.gw_provider_instance_ip = _gw_vm_details['public_v4']

                    _sec_groups = new_conn.list_security_groups(filters={ "tenant_id" : new_project.id, "name" : "default"})
                    for _sec_group_rule in _sec_groups[0].security_group_rules:
                        new_conn.delete_security_group_rule(_sec_group_rule['id'])
                    new_project.sec_group_id = _sec_groups[0].id
                    # CreateInternal SSH security Group Rule
                    internal_ssh_rule_id = new_conn.create_security_group_rule(new_project.sec_group_id,
                    port_range_min=22,
                    port_range_max=22,
                    protocol="tcp",
                    remote_ip_prefix="192.168.3.0/24",
                    project_id=new_project.id
                    )
                    internal_av_firewall_rule_id = new_conn.create_security_group_rule(new_project.sec_group_id,
                    port_range_min=4118,
                    port_range_max=4118,
                    protocol="tcp",
                    remote_ip_prefix="0.0.0.0/0",
                    project_id=new_project.id
                    )
                    internal_monitoring_firewall_rule_id = new_conn.create_security_group_rule(new_project.sec_group_id,
                    port_range_min=9100,
                    port_range_max=9100,
                    protocol="tcp",
                    remote_ip_prefix="0.0.0.0/0",
                    project_id=new_project.id
                    )
                    internal_egress_rule_id = new_conn.create_security_group_rule(new_project.sec_group_id,
                    port_range_min=1,
                    port_range_max=65535,
                    protocol="tcp",
                    direction="egress",
                    remote_ip_prefix="0.0.0.0/0",
                    project_id=new_project.id
                    )
                    new_project.internal_ssh_rule_id = internal_ssh_rule_id
                    return new_project
                else:
                    return None



            return check_project_status(stack_name)
        except Exception as e:
            log.info("Exception: %s", e)
            return None
            # abort(
            #     code=HTTPStatus.UNPROCESSABLE_ENTITY,
            #     message="%s" % e
            # )
    def create_volume(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_volume(kwargs['volume_size'], 
                wait=True, 
                timeout=None, 
                image=kwargs['image'], 
                bootable=kwargs['bootable'], 
                name=kwargs['name'])
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_volume(self, provider, volume_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.get_volume(volume_id, filters=None)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_volume(self, provider, volume_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_volume(volume_id)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_volume_snapshots(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.list_volume_snapshots(detailed=kwargs['detailed'], search_opts=kwargs['search_opts'])
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_volume_snapshot(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_volume_snapshot(kwargs['provider_volume_id'], description=kwargs['description'], force=False, wait=True, timeout=None)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_volume_snapshot_by_id(self, provider, volume_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.get_volume_snapshot_by_id(volume_id)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_volume_snapshot(self, provider, volume_id, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_volume_snapshot(volume_id, wait=False, timeout=3600)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def attach_volume(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.attach_volume(kwargs['server'], kwargs['volume'], 
                device=kwargs['device'], 
                wait=True, 
                timeout=3600)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def detach_volume(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.detach_volume(kwargs['server'], kwargs['volume'], 
                wait=True, 
                timeout=3600)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_limits(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.compute.get_limits()
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_load_balancer(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            new_lb = types.SimpleNamespace()
            new_conn = conn.connect_as_project(kwargs['project_name'])
            lb_parameters = { 
            "internal_network_id" : kwargs['project_name'] + "_int_net",
            "public_net_name" : kwargs['external_network'],
            "sec_group_name" : kwargs['lb_name'] + "_sec_group",
            "docker_registry" : provider.docker_registry,
            "lb_vm_name": kwargs['lb_name'] + "_vm"
            }
            lb_template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates/openstack', "create_project_lb.yaml"))
            _lb_vm = new_conn.create_stack(kwargs['lb_name'] + "_lb", tags=None, template_file=lb_template_path, template_url=None, template_object=None, files=None, rollback=True, wait=True, timeout=3600, environment_files=None, **lb_parameters)

            log.info(_lb_vm)
            if 'stack_status' in _lb_vm and _lb_vm.stack_status == 'CREATE_COMPLETE':
                try:
                    for lb_resources in _lb_vm.outputs:
                        if lb_resources.output_key == 'internal_security_group_id':
                            new_lb.lb_sec_group_id = lb_resources.output_value
                        elif lb_resources.output_key == 'lb_vm_id':
                            new_lb.lb_provider_instance_id = lb_resources.output_value
                except:
                    for lb_resources in _lb_vm['outputs']:
                        if lb_resources['output_key'] == 'internal_security_group_id':
                            new_lb.lb_sec_group_id = lb_resources['output_value']
                        elif lb_resources['output_key'] == 'lb_vm_id':
                            new_lb.lb_provider_instance_id = lb_resources['output_value']

                _lb_vm_details = new_conn.get_server_by_id(new_lb.lb_provider_instance_id)
                new_lb.lb_provider_instance_ip = _lb_vm_details.public_v4

            return new_lb

        except Exception as e:
            log.info("Exception: %s", e)
            return None
            # abort(
            #     code=HTTPStatus.UNPROCESSABLE_ENTITY,
            #     message="%s" % e
            # )
    def create_bucket(self, provider, name, **kwargs):
        try:
            conn = self.connect(provider)
            public = False
            if 'public' in kwargs:
                public = kwargs['public']
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_container(name, public=public)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_buckets(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            full_listing = True
            if 'full_listing' in kwargs:
                full_listing = kwargs['full_listing']
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.list_containers(full_listing=full_listing)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def create_object(self, provider, bucket, name, **kwargs):
        try:
            conn = self.connect(provider)

            filename = None
            md5 = None
            sha256 = None
            segment_size = None
            use_slo = True
            metadata = None
            if 'filename' in kwargs:
                filename = kwargs['filename']
            if 'md5' in kwargs:
                md5 = kwargs['md5']
            if 'sha256' in kwargs:
                sha256 = kwargs['sha256']
            if 'segment_size' in kwargs:
                segment_size = kwargs['segment_size']
            if 'use_slo' in kwargs:
                use_slo = kwargs['use_slo']
            if 'metadata' in kwargs:
                metadata = kwargs['metadata']
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.create_object(bucket, name, filename=filename, md5=md5, sha256=sha256, segment_size=segment_size, use_slo=use_slo, metadata=metadata)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def list_objects(self, provider, bucket, **kwargs):
        try:
            conn = self.connect(provider)
            full_listing = True
            if 'full_listing' in kwargs:
                full_listing = kwargs['full_listing']
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.list_objects(bucket, full_listing=full_listing)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def get_object(self, provider, bucket, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.get_object(bucket, name, query_string=None, resp_chunk_size=1024, outfile=None)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def update_object(self, provider, bucket, name, **kwargs):
        try:
            conn = self.connect(provider)
            metadata = None
            if 'metadata' in kwargs:
                metadata = kwargs['metadata']
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.update_object(bucket, name, metadata=metadata, **headers)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )
    def delete_object(self, provider, bucket, name, **kwargs):
        try:
            conn = self.connect(provider)
            if 'project_name' in kwargs:
                conn = conn.connect_as_project(kwargs['project_name'])
            return conn.delete_object(bucket, name)
        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )


    def create_server_group(self, provider,  **kwargs):

        ticket_id = None
        new_server_group = types.SimpleNamespace()
        try:
            conn = self.connect(provider)
            new_conn = conn.connect_as_project(kwargs['project_name'])
            server_parameters = {
                "stackname": kwargs['stackname'],
                "image": kwargs['image'],
                "flavor": kwargs['flavor'],
                "private_network": kwargs['private_network'],
                "public_network": kwargs['public_network'],
                "docker_registry": provider.docker_registry,
                "cluster_size": kwargs['cluster_size'],
                "lb_sec_group_name": kwargs['lb_sec_group_name'],
                "lb_vm_name": kwargs['lb_vm_name'],
                "lb_private_network":kwargs['lb_private_network'],
                "boot_vol_size": kwargs['boot_vol_size']
                # "lb_flavor": kwargs['lb_flavor'],
                # "lb_image": kwargs['lb_image']
            }
            lb_template_path = os.path.abspath( os.path.join(os.path.dirname(__file__), 'templates/openstack', "serverGroup.yaml"))
            env_path = os.path.abspath( os.path.join(os.path.dirname(__file__), 'templates/openstack', "env.yaml"))

            _lb_vm = new_conn.create_stack(kwargs['stackname'], tags=None, template_file=lb_template_path, template_url=None, template_object=None, files=None, rollback=True, wait=True, timeout=3600, environment_files=[env_path], **server_parameters)
            ticket_id = _lb_vm.id

            try:
                if _lb_vm.stack_status == 'CREATE_COMPLETE':
                    for lb_resources in _lb_vm.outputs:
                        if lb_resources['output_key'] == 'internal_security_group_id':
                            new_server_group.lb_sec_group_id = lb_resources['output_value']
                        elif lb_resources['output_key'] == 'lb_vm_id':
                            new_server_group.lb_provider_instance_id = lb_resources['output_value']
                        elif lb_resources['output_key'] == 'server_id':
                            new_server_group.server_id = lb_resources['output_value']
                        elif lb_resources['output_key'] == 'server_ip':
                            new_server_group.server_ip = lb_resources['output_value']
                        elif lb_resources['output_key'] == 'server_name':
                            new_server_group.server_name = lb_resources['output_value']
                    _lb_vm_details = new_conn.get_server_by_id(new_server_group.lb_provider_instance_id)
                    new_server_group.lb_provider_instance_ip = _lb_vm_details.public_v4
                else:
                    new_server_group.ticket_id = ticket_id
                    return new_server_group

            except Exception as e:
                log.info("Stack Exception: %s", e)
                new_server_group.ticket_id = ticket_id
                return new_server_group
            log.info(new_server_group)
            return new_server_group

        except Exception as e:
            log.info("Exception: %s", e)
            new_server_group.ticket_id = ticket_id
            return new_server_group
            # abort(
            #     code=HTTPStatus.UNPROCESSABLE_ENTITY,
            #     message="%s" % e
            # )


    def update_server_group(self, provider, **kwargs):
        try:
            conn = self.connect(provider)
            updated_server_group = types.SimpleNamespace()
            conn = conn.connect_as_project(kwargs['project_name'])
            #new_conn = conn.connect_as_project(kwargs['project_name'])
            # parameters = {
            #     "cluster_size": kwargs['cluster_size'],
            #     "flavor": kwargs['flavor']
            # }
            log.info(kwargs['private_network'])
            parameters = {
                "stackname": kwargs['stackname'],
                "image": kwargs['image'],
                "flavor": kwargs['flavor'],
                # "private_network": kwargs['private_network'],
                # "public_network": kwargs['public_network'],
                "cluster_size": kwargs['cluster_size'],
                "lb_sec_group_name": kwargs['lb_sec_group_name'],
                "lb_vm_name": kwargs['lb_vm_name'],
                "lb_private_network": kwargs['lb_private_network'],
            }
            lb_template_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), 'templates/openstack', "serverGroup.yaml"))
            env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates/openstack', "env.yaml"))

            _server_response = conn.update_stack(kwargs['stackname'], template_file=lb_template_path,
                                           template_url=None, template_object=None, files=None, rollback=True,
                                           wait=True, timeout=3600, environment_files=[env_path], **parameters)
            # lb_template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates/openstack', "serverGroupAIO.yaml"))
            # _server_response = conn.update_stack(kwargs['stackname'], template_file=lb_template_path, template_url=None,
            #                   template_object=None, files=None, rollback=True, wait=True, timeout=3600, environment_files=None,
            #                   **parameters)
            log.info(_server_response)
            new_server_group = types.SimpleNamespace()

            for lb_resources in _server_response.outputs:
                if lb_resources['output_key'] == 'internal_security_group_id':
                    new_server_group.lb_sec_group_id = lb_resources['output_value']
                elif lb_resources['output_key'] == 'lb_vm_id':
                    new_server_group.lb_provider_instance_id = lb_resources['output_value']
                elif lb_resources['output_key'] == 'server_id':
                    new_server_group.server_id = lb_resources['output_value']
                elif lb_resources['output_key'] == 'server_ip':
                    new_server_group.server_ip = lb_resources['output_value']
                elif lb_resources['output_key'] == 'server_name':
                    new_server_group.server_name = lb_resources['output_value']

            _lb_vm_details = conn.get_server_by_id(new_server_group.lb_provider_instance_id)
            new_server_group.lb_provider_instance_ip = _lb_vm_details.public_v4
            return new_server_group

        except Exception as e:
            log.info("Exception: %s", e)
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                message="%s" % e
            )


    def delete_server_group(self, provider, name_or_id, **kwargs):
        conn = self.connect(provider)
        #updated_server_group = types.SimpleNamespace()
        conn = conn.connect_as_project(kwargs['project_name'])
        _server_response = conn.delete_stack(name_or_id, wait=True)
        return _server_response
        
    def set_server_metadata(self, provider, name_or_id, **kwargs):
        conn = self.connect(provider)
        #updated_server_group = types.SimpleNamespace()
        conn = conn.connect_as_project(kwargs['project_name'])
        _server_response = conn.set_server_metadata(name_or_id, metadata=kwargs['metadata'])
        return _server_response
        
    def delete_server_metadata(self, provider, name_or_id, **kwargs):
        conn = self.connect(provider)
        #updated_server_group = types.SimpleNamespace()
        conn = conn.connect_as_project(kwargs['project_name'])
        _server_response = conn.set_server_metadata(name_or_id, metadata_keys=kwargs['metadata_keys'])
        return _server_response


    def add_network_to_server(self, provider, **kwargs):
        conn = self.connect(provider)
        conn = conn.connect_as_project(kwargs['project_name'])
        _response = conn.compute.create_server_interface(kwargs['server_id'], net_id=kwargs['network_id'])
        return _response

    def remove_network_to_server(self, provider, **kwargs):
        conn = self.connect(provider)
        conn = conn.connect_as_project(kwargs['project_name'])
        _response = conn.compute.delete_server_interface(kwargs['interface_id'],kwargs['server_id'])

        return _response

    def create_network_port(self, provider, **kwargs):
        conn = self.connect(provider)
        conn = conn.connect_as_project(kwargs['project_name'])

        _response = conn.network.create_port(project_id=kwargs['project_id'], network_id=kwargs['network_id'], security_groups=[kwargs['sec_group_id']])
        return _response


    def get_stack_details(self, provider, **kwargs):
        conn = self.connect(provider)
        new_conn = conn.connect_as_project(kwargs['project_name'])
        stack_details = new_conn.get_server_group(kwargs['stack_id'])
        log.info(stack_details)
        return stack_details


    def add_interface_to_router(self, provider, **kwargs):
        conn = self.connect(provider)
        new_conn = conn.connect_as_project(kwargs['project_name'])

        router = new_conn.get_router(kwargs['router'], filters=None)
        log.info(router)
        response = new_conn.add_router_interface(router, subnet_id=kwargs['subnet_id'], port_id=None)
        log.info(response)
        return response

    def get_router(self, provider, **kwargs):
        conn = self.connect(provider)
        new_conn = conn.connect_as_project(kwargs['project_name'])
        response = new_conn.get_router(kwargs['router_id'], filters=None)
        log.info(response)
        return response

    def attach_security_groups(self, provider, **kwargs):
        conn = self.connect(provider)
        new_conn = conn.connect_as_project(kwargs['project_name'])
        log.info(kwargs['security_groups'])
        response = new_conn.add_server_security_groups(kwargs['server'], kwargs['security_groups'])
        return response

    def detach_security_groups(self, provider, **kwargs):
        conn = self.connect(provider)
        new_conn = conn.connect_as_project(kwargs['project_name'])
        response = new_conn.remove_server_security_groups(kwargs['server'], kwargs['security_groups'])
        return response