# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
import unittest, logging, os, shutil, json
from itertools import chain
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
        assert harness.charm.RouterProvider.get_routing_table() == {}

    def test_provider_adds_new_relation(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Get routing table
        expected_rt = {"ip-router-requirer": {"networks": []}}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt

    def test_provider_adds_new_network(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Update databag
        network_request = [{"network": "192.168.250.0/24", "gateway": "192.168.250.1"}]
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )

        # Get routing table
        expected_rt = {"ip-router-requirer": json.dumps(network_request)}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(network_request)}
        assert harness.get_relation_data(rel_id, harness.charm.app.name) == expected_databag

    def test_provider_adds_new_network_with_route(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Update databag with a network with route
        network_request = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            }
        ]
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )

        # Get routing table
        expected_rt = {"ip-router-requirer": json.dumps(network_request)}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(network_request)}
        assert harness.get_relation_data(rel_id, harness.charm.app.name) == expected_databag

    def test_provider_adds_multiple_networks_from_same_relation(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Update databag
        network_request = [
            {"network": "192.168.250.0/24", "gateway": "192.168.250.1"},
            {"network": "192.168.251.0/24", "gateway": "192.168.251.1"},
        ]
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )

        # Get routing table
        expected_rt = {"ip-router-requirer": json.dumps(network_request)}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(network_request)}
        assert harness.get_relation_data(rel_id, harness.charm.app.name) == expected_databag

    def test_provider_adds_multiple_networks_from_multiple_relations(self):
        harness = self._setup()

        # Create relation 1
        rel_a_id = harness.add_relation("ip-router", "ip-router-requirer-a")
        harness.add_relation_unit(rel_a_id, "ip-router-requirer-a/0")

        # Create relation 2
        rel_b_id = harness.add_relation("ip-router", "ip-router-requirer-b")
        harness.add_relation_unit(rel_b_id, "ip-router-requirer-b/0")

        # Create relation 3
        rel_c_id = harness.add_relation("ip-router", "ip-router-requirer-c")
        harness.add_relation_unit(rel_c_id, "ip-router-requirer-c/0")

        # Update databag 1 with a network with route
        network_request_a = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            }
        ]

        harness.update_relation_data(
            rel_a_id, "ip-router-requirer-a", {"networks": json.dumps(network_request_a)}
        )

        # Update databag 2 with a network
        network_request_b = [
            {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        ]

        harness.update_relation_data(
            rel_b_id, "ip-router-requirer-b", {"networks": json.dumps(network_request_b)}
        )

        # Update databag 3 with a network
        network_request_c = [
            {
                "network": "192.168.251.0/24",
                "gateway": "192.168.251.1",
            }
        ]

        harness.update_relation_data(
            rel_c_id, "ip-router-requirer-c", {"networks": json.dumps(network_request_c)}
        )

        # Get routing table
        expected_rt = {
            "ip-router-requirer-a": json.dumps(network_request_a),
            "ip-router-requirer-b": json.dumps(network_request_b),
            "ip-router-requirer-c": json.dumps(network_request_c),
        }
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {
            "networks": json.dumps(
                list(chain(network_request_a, network_request_b, network_request_c))
            )
        }
        assert harness.get_relation_data(rel_a_id, harness.charm.app.name) == expected_databag
        assert harness.get_relation_data(rel_b_id, harness.charm.app.name) == expected_databag
        assert harness.get_relation_data(rel_c_id, harness.charm.app.name) == expected_databag

    def test_provider_removes_networks_on_relation_departed(self):
        harness = self._setup()

        # Create relation 1
        rel_a_id = harness.add_relation("ip-router", "ip-router-requirer-a")
        harness.add_relation_unit(rel_a_id, "ip-router-requirer-a/0")

        # Create relation 2
        rel_b_id = harness.add_relation("ip-router", "ip-router-requirer-b")
        harness.add_relation_unit(rel_b_id, "ip-router-requirer-b/0")

        # Update databag 1 with a network with route
        network_request_a = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            }
        ]

        harness.update_relation_data(
            rel_a_id, "ip-router-requirer-a", {"networks": json.dumps(network_request_a)}
        )

        # Update databag 2 with a network
        network_request_b = [
            {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        ]

        harness.update_relation_data(
            rel_b_id, "ip-router-requirer-b", {"networks": json.dumps(network_request_b)}
        )

        # Remove relation 1
        harness.remove_relation_unit(rel_a_id, "ip-router-requirer-a/0")

        # Get routing table
        expected_rt = {
            "ip-router-requirer-b": json.dumps(network_request_b),
        }
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(network_request_b)}
        assert harness.get_relation_data(rel_b_id, harness.charm.app.name) == expected_databag


class TestRequirer(unittest.TestCase):
    def _setup(self):
        # Set Up
        harness = Harness(SimpleIPRouteRequirerCharm)
        harness.set_model_name("test")
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader()
        return harness

    def test_get_routing_table(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        assert harness.charm.RouterRequirer.get_all_networks() == []

    def test_request_new_network(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        ]
        harness.charm.RouterRequirer.request_network(network_request)

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps(network_request)
        }

    def test_request_new_network_multiple(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {"network": "192.168.252.0/24", "gateway": "192.168.252.1"},
            {"network": "192.168.250.0/24", "gateway": "192.168.250.1"},
        ]
        harness.charm.RouterRequirer.request_network(network_request)

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps(network_request)
        }

    def test_request_new_network_with_ip_conflicts(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Create existing network
        existing_network = [{"network": "192.168.252.0/24", "gateway": "192.168.252.1"}]
        harness.update_relation_data(
            rel_id, "ip-router-provider", {"networks": json.dumps(existing_network)}
        )

        # Request a network
        network_request = [
            {"network": "192.168.240.0/20", "gateway": "192.168.250.1"},
        ]
        harness.charm.RouterRequirer.request_network(network_request)
        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps([])
        }

    def test_request_new_network_with_unreachable_route(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Create existing network
        existing_network = [{"network": "192.168.252.0/24", "gateway": "192.168.252.1"}]
        harness.update_relation_data(
            rel_id, "ip-router-provider", {"networks": json.dumps(existing_network)}
        )

        # Request a network
        network_request = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.240.3"}],
            }
        ]
        harness.charm.RouterRequirer.request_network(network_request)
        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps([])
        }

    def test_request_new_network_multiple_with_one_invalid(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation("ip-router", "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Create existing network
        existing_network = [{"network": "192.168.252.0/24", "gateway": "192.168.252.1"}]
        harness.update_relation_data(
            rel_id, "ip-router-provider", {"networks": json.dumps(existing_network)}
        )

        # Request a network
        network_request = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.240.3"}],
            },
            {
                "network": "192.168.251.0/24",
                "gateway": "192.168.251.1",
            },
        ]
        harness.charm.RouterRequirer.request_network(network_request)
        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps([network_request[1]])
        }
