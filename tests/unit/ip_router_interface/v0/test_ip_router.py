# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
import unittest, logging, os, shutil, json
from unittest.mock import Mock
from ops.testing import Harness

from tests.provider_charm.src.charm import SimpleIPRouteProviderCharm
from tests.requirer_charm.src.charm import SimpleIPRouteRequirerCharm

logger = logging.getLogger(__name__)

LIB_DIR = "lib/charms/ip_router_interface/v0"
LIB_NAME = "ip_router_interface.py"
REQUIRER_CHARM_DIR = "tests/requirer_charm"
PROVIDER_CHARM_DIR = "tests/provider_charm"
IP_ROUTER_PROVIDER_APP_NAME = "ip-router-provider"
IP_ROUTER_REQUIRER_APP_NAME = "ip-router-requirer"


def copy_lib_content() -> None:
    os.makedirs(f"{REQUIRER_CHARM_DIR}/{LIB_DIR}", exist_ok=True)
    os.makedirs(f"{PROVIDER_CHARM_DIR}/{LIB_DIR}", exist_ok=True)
    shutil.copyfile(src=f"{LIB_DIR}/{LIB_NAME}", dst=f"{REQUIRER_CHARM_DIR}/{LIB_DIR}/{LIB_NAME}")
    shutil.copyfile(src=f"{LIB_DIR}/{LIB_NAME}", dst=f"{PROVIDER_CHARM_DIR}/{LIB_DIR}/{LIB_NAME}")


class TestProvider(unittest.TestCase):
    def _setup(self):
        # Set Up
        harness = Harness(SimpleIPRouteProviderCharm)
        harness.set_model_name("test")
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader()
        return harness

    def test_provider_initial_setup(self):
        harness = self._setup()

        # Check initial routing table
        event = Mock()
        harness.charm._action_get_routing_table(event=event)
        event.set_results.assert_called_with({"msg": "{}"})

    def test_provider_adds_new_network(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Get routing table
        expected_rt = {"ip-router-requirer/0": {"networks": []}}
        event = Mock()
        harness.charm._action_get_routing_table(event=event)
        event.set_results.assert_called_with({"msg": json.dumps(expected_rt)})

    def test_provider_adds_new_network(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Receive a new route request
        event = Mock()
        event.params = {"network": "192.168.250.1/24"}
        event.unit.name = "ip-router-requirer/0"
        harness.charm.RouterProvider._on_new_network_request(event=event)

        # Get routing table
        expected_rt = {
            "ip-router-requirer/0": {
                "networks": [{"network": "192.168.250.0/24", "gateway": "192.168.250.1"}]
            }
        }
        event = Mock()
        harness.charm._action_get_routing_table(event=event)
        event.set_results.assert_called_with({"msg": json.dumps(expected_rt)})

    def test_provider_adds_new_route(self):
        pass

    def test_provider_shares_networks_with_all_relations(self):
        pass


class TestRequirer(unittest.TestCase):
    pass
