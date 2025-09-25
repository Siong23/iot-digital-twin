"""Stop packet capture for the iot simulation topology (iot digital twin)."""

import re
import sys
import time

#import docker

from gns3utils import *

PROJECT_NAME = "testbed"

check_resources()
check_local_gns3_config()
server = Server(*read_local_gns3_config())

check_server_version(server)

project = get_project_by_name(server, PROJECT_NAME)

if project:
    print(f"Project {PROJECT_NAME} exists. ", project)
else:
    print(f"Project {PROJECT_NAME} does not exsist!")
    sys.exit(1)

if len(get_all_nodes(server, project)) == 0:
    print(f"Project {PROJECT_NAME} is empty!")
    sys.exit(1)

check_ipaddrs(server, project)

#docker_client = docker.from_env()
#docker_client.ping()

##############################################################
# Stop packet capturing and all the nodes #
##############################################################

stop_capture_all_iot_links(server, project, re.compile("openvswitch-1", re.IGNORECASE), re.compile("IoTConsumer|DigitalIoTBroker-Server", re.IGNORECASE))
stop_capture_all_iot_links(server, project, re.compile("openvswitch-2", re.IGNORECASE), re.compile("DigitalIPCamera|TemperatureHumiditySensor|GatewayDigitalTwin", re.IGNORECASE))
