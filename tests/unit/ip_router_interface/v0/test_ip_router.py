# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
import json
import logging
import os
import shutil
import unittest
from itertools import chain

from ops.testing import Harness

from tests.provider_charm.src.charm import (
    IP_ROUTER_PROVIDER_RELATION_NAME,
    SimpleIPRouteProviderCharm,
)
from tests.requirer_charm.src.charm import (
    IP_ROUTER_REQUIRER_RELATION_NAME,
    SimpleIPRouteRequirerCharm,
)

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
        copy_lib_content()
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
        rel_id = harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")
        # Create a new relation with a different name

        # Get routing table
        expected_rt = {}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt

    def test_provider_adds_new_network(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Update databag
        network_request = [{"network": "192.168.250.0/24", "gateway": "192.168.250.1"}]
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"network-name": IP_ROUTER_REQUIRER_RELATION_NAME}
        )

        # Get routing table
        expected_rt = {IP_ROUTER_REQUIRER_RELATION_NAME: network_request}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(network_request)}
        assert harness.get_relation_data(rel_id, harness.charm.app.name) == expected_databag

    def test_provider_adds_new_network_with_route(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer")
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
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"network-name": IP_ROUTER_REQUIRER_RELATION_NAME}
        )

        # Get routing table
        expected_rt = {IP_ROUTER_REQUIRER_RELATION_NAME: network_request}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(network_request)}
        assert harness.get_relation_data(rel_id, harness.charm.app.name) == expected_databag

    def test_provider_adds_multiple_networks_from_same_relation(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer")
        harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        # Update databag
        network_request = [
            {"network": "192.168.250.0/24", "gateway": "192.168.250.1"},
            {"network": "192.168.251.0/24", "gateway": "192.168.251.1"},
        ]
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )
        harness.update_relation_data(
            rel_id, "ip-router-requirer", {"network-name": IP_ROUTER_REQUIRER_RELATION_NAME}
        )
        # Get routing table
        expected_rt = {IP_ROUTER_REQUIRER_RELATION_NAME: network_request}
        assert harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(network_request)}
        assert harness.get_relation_data(rel_id, harness.charm.app.name) == expected_databag

    def test_provider_adds_multiple_networks_from_multiple_relations(self):
        harness = self._setup()

        # Create relation 1
        rel_a_id = harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer-a")
        harness.add_relation_unit(rel_a_id, "ip-router-requirer-a/0")

        # Create relation 2
        rel_b_id = harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer-b")
        harness.add_relation_unit(rel_b_id, "ip-router-requirer-b/0")

        # Create relation 3
        rel_c_id = harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer-c")
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
        harness.update_relation_data(
            rel_a_id,
            "ip-router-requirer-a",
            {"network-name": f"{IP_ROUTER_REQUIRER_RELATION_NAME}-a"},
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
        harness.update_relation_data(
            rel_b_id,
            "ip-router-requirer-b",
            {"network-name": f"{IP_ROUTER_REQUIRER_RELATION_NAME}-b"},
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
        harness.update_relation_data(
            rel_c_id,
            "ip-router-requirer-c",
            {"network-name": f"{IP_ROUTER_REQUIRER_RELATION_NAME}-c"},
        )

        # Get routing table
        expected_rt = {
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-a": network_request_a,
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-b": network_request_b,
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-c": network_request_c,
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


class TestRequirer(unittest.TestCase):
    def _setup(self):
        copy_lib_content()
        harness = Harness(SimpleIPRouteRequirerCharm)
        harness.set_model_name("test")
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader()
        return harness

    def test_get_routing_table(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        assert harness.charm.RouterRequirer.get_all_networks() == []

    def test_get_routing_table_multiple_networks(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Create existing network
        existing_network = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            },
            {"network": "192.168.252.0/24", "gateway": "192.168.252.1"},
            {"network": "192.168.251.0/24", "gateway": "192.168.251.1/24"},
        ]

        harness.update_relation_data(
            rel_id, "ip-router-provider", {"networks": json.dumps(existing_network)}
        )

        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        assert harness.charm.RouterRequirer.get_all_networks() == existing_network

    def test_get_routing_table_multiple_networks_and_providers(self):
        harness = self._setup()

        # Create relation 1
        rel_1_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider-a")
        harness.add_relation_unit(rel_1_id, "ip-router-provider-a/0")

        # Create relation 2
        rel_2_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider-b")
        harness.add_relation_unit(rel_2_id, "ip-router-provider-b/0")

        # Create network 1
        existing_network_1 = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            }
        ]
        harness.update_relation_data(
            rel_1_id, "ip-router-provider-a", {"networks": json.dumps(existing_network_1)}
        )
        # Create network 2
        existing_network_2 = [
            {"network": "192.168.252.0/24", "gateway": "192.168.252.1"},
            {"network": "192.168.251.0/24", "gateway": "192.168.251.1/24"},
        ]
        harness.update_relation_data(
            rel_2_id, "ip-router-provider-b", {"networks": json.dumps(existing_network_2)}
        )
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        assert (
            harness.charm.RouterRequirer.get_all_networks()
            == existing_network_1 + existing_network_2
        )

    def test_request_new_network(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        harness.charm.RouterRequirer.request_network(network_request)

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps(network_request),
            "network-name": IP_ROUTER_REQUIRER_RELATION_NAME,
        }

    def test_request_new_network_multiple(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {"network": "192.168.252.0/24", "gateway": "192.168.252.1"},
            {"network": "192.168.250.0/24", "gateway": "192.168.250.1"},
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        harness.charm.RouterRequirer.request_network(network_request)

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps(network_request),
            "network-name": IP_ROUTER_REQUIRER_RELATION_NAME,
        }

    def test_request_new_network_missing_relation(self):
        harness = self._setup()

        # Request a network
        network_request = [
            {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except RuntimeError as e:
            assert e.args[0] == "No ip-router relation exists yet."

    def test_request_new_network_with_ip_conflicts(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Create existing network
        existing_network = [{"network": "192.168.252.0/24", "gateway": "192.168.252.1"}]
        harness.update_relation_data(
            rel_id,
            "ip-router-provider",
            {"networks": json.dumps(existing_network)},
        )

        # Request a network
        network_request = [
            {"network": "192.168.240.0/20", "gateway": "192.168.250.1"},
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except ValueError as e:
            assert e.args[0] == "This network has been defined in a previous entry."

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_request_new_network_with_unreachable_route(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
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
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except ValueError as e:
            assert e.args[0] == "There is no route to this destination from the network."
        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_request_new_network_multiple_with_one_invalid(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
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
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except ValueError as e:
            assert e.args[0] == "There is no route to this destination from the network."
        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_request_new_network_no_gateway(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {"network": "192.168.240.0/20", "sad": "192.168.250.1"},
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except KeyError as e:
            assert e.args[0] == "Key 'gateway' not found."

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_request_new_network_no_network(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {"sad": "192.168.240.0/20", "gateway": "192.168.250.1"},
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except KeyError as e:
            assert e.args[0] == "Key 'network' not found."

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_request_new_network_no_route_destination(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destinope": "172.250.0.0/16", "gateway": "192.168.240.3"}],
            }
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except KeyError as e:
            assert e.args[0] == "Key 'destination' not found in route."

        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_request_new_network_no_route_gateway(self):
        harness = self._setup()

        # Create a relation
        rel_id = harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        harness.add_relation_unit(rel_id, "ip-router-provider/0")

        # Request a network
        network_request = [
            {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateroad": "192.168.240.3"}],
            }
        ]
        harness.charm.RouterRequirer.relationship_name = IP_ROUTER_REQUIRER_RELATION_NAME
        try:
            harness.charm.RouterRequirer.request_network(network_request)
        except KeyError as e:
            assert e.args[0] == "Key 'gateway' not found in route."
        assert harness.get_relation_data(rel_id, "ip-router-requirer") == {}
