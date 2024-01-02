# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import os
import shutil
import unittest

from ops.testing import Harness

from tests.provider_charm.src.charm import (
    IP_ROUTER_PROVIDER_RELATION_NAME,
    SimpleIPRouteProviderCharm,
)
from tests.requirer_charm.src.charm import (
    IP_ROUTER_REQUIRER_RELATION_NAME,
    SimpleIPRouteRequirerCharm,
)

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
    def setUp(self):
        copy_lib_content()
        harness = Harness(SimpleIPRouteProviderCharm)
        harness.set_model_name("test")
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader()
        self.harness = harness

    def test_provider_initial_setup(self):
        # Check initial routing table
        assert self.harness.charm.RouterProvider.get_routing_table() == {}

    def test_given_provider_when_network_request_received_then_adds_network(self):
        rel_id = self.harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer")
        self.harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        network_request = {
            IP_ROUTER_REQUIRER_RELATION_NAME: {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
            }
        }
        self.harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )

        assert self.harness.charm.RouterProvider.get_routing_table() == network_request

    def test_given_provider_when_network_request_with_provider_received_then_adds_network(self):
        rel_id = self.harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer")
        self.harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        network_request = {
            IP_ROUTER_REQUIRER_RELATION_NAME: {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            }
        }
        self.harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )

        assert self.harness.charm.RouterProvider.get_routing_table() == network_request

    def test_given_provider_when_multiple_network_requests_received_then_adds_networks(self):
        rel_id = self.harness.add_relation(IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer")
        self.harness.add_relation_unit(rel_id, "ip-router-requirer/0")

        network_request = {
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-a": {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
            },
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-b": {
                "network": "192.168.251.0/24",
                "gateway": "192.168.251.1",
            },
        }
        self.harness.update_relation_data(
            rel_id, "ip-router-requirer", {"networks": json.dumps(network_request)}
        )
        assert self.harness.charm.RouterProvider.get_routing_table() == network_request

    def test_given_provider_when_requests_from_multiple_relations_then_adds_networks(self):
        rel_a_id = self.harness.add_relation(
            IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer-a"
        )
        self.harness.add_relation_unit(rel_a_id, "ip-router-requirer-a/0")

        rel_b_id = self.harness.add_relation(
            IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer-b"
        )
        self.harness.add_relation_unit(rel_b_id, "ip-router-requirer-b/0")

        rel_c_id = self.harness.add_relation(
            IP_ROUTER_PROVIDER_RELATION_NAME, "ip-router-requirer-c"
        )
        self.harness.add_relation_unit(rel_c_id, "ip-router-requirer-c/0")

        network_request_a = {
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-a": {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            }
        }

        self.harness.update_relation_data(
            rel_a_id, "ip-router-requirer-a", {"networks": json.dumps(network_request_a)}
        )

        network_request_b = {
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-b": {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        }

        self.harness.update_relation_data(
            rel_b_id, "ip-router-requirer-b", {"networks": json.dumps(network_request_b)}
        )

        network_request_c = {
            f"{IP_ROUTER_REQUIRER_RELATION_NAME}-c": {
                "network": "192.168.251.0/24",
                "gateway": "192.168.251.1",
            }
        }

        self.harness.update_relation_data(
            rel_c_id, "ip-router-requirer-c", {"networks": json.dumps(network_request_c)}
        )

        expected_rt = dict(network_request_a | network_request_b | network_request_c)
        assert self.harness.charm.RouterProvider.get_routing_table() == expected_rt
        expected_databag = {"networks": json.dumps(expected_rt)}
        assert (
            self.harness.get_relation_data(rel_a_id, self.harness.charm.app.name)
            == expected_databag
        )
        assert (
            self.harness.get_relation_data(rel_b_id, self.harness.charm.app.name)
            == expected_databag
        )
        assert (
            self.harness.get_relation_data(rel_c_id, self.harness.charm.app.name)
            == expected_databag
        )


class TestRequirer(unittest.TestCase):
    def setUp(self):
        copy_lib_content()
        harness = Harness(SimpleIPRouteRequirerCharm)
        harness.set_model_name("test")
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader()
        self.harness = harness

    def test_given_no_relations_when_get_routing_table_then_return_empty_list(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        assert self.harness.charm.RouterRequirer.get_routing_table() == {}

    def test_given_filled_routing_table_when_get_routing_table_then_gets_network_correctly(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        existing_network = {
            "host-a": {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
            },
            "host-b": {"network": "192.168.252.0/24", "gateway": "192.168.252.1"},
            "host-c": {"network": "192.168.251.0/24", "gateway": "192.168.251.1"},
        }

        self.harness.update_relation_data(
            rel_id,
            "ip-router-provider",
            {"networks": json.dumps(existing_network)},
        )

        assert self.harness.charm.RouterRequirer.get_routing_table() == existing_network

    def test_given_requirer_when_request_new_network_then_produces_correct_databag(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        network_request = {
            "host-a": {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        }
        self.harness.charm.RouterRequirer.request_network(network_request)

        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps(network_request),
        }

    def test_given_requirer_when_request_new_network_multiple_then_produces_correct_databag(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        network_request = {
            "host-a": {"network": "192.168.252.0/24", "gateway": "192.168.252.1"},
            "host-b": {"network": "192.168.250.0/24", "gateway": "192.168.250.1"},
        }
        self.harness.charm.RouterRequirer.request_network(network_request)

        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {
            "networks": json.dumps(network_request),
        }

    def test_given_requirer_when_request_new_network_missing_relation_then_returns_none(self):
        network_request = {
            "host-a": {
                "network": "192.168.252.0/24",
                "gateway": "192.168.252.1",
            }
        }
        assert self.harness.charm.RouterRequirer.request_network(network_request) is None

    def test_given_requirer_when_request_new_network_with_ip_conflicts_then_raises_exception(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        existing_network = {"host-a": {"network": "192.168.252.0/24", "gateway": "192.168.252.1"}}
        self.harness.update_relation_data(
            rel_id,
            "ip-router-provider",
            {"networks": json.dumps(existing_network)},
        )

        network_request = {
            "host-b": {"network": "192.168.240.0/20", "gateway": "192.168.250.1"},
        }
        with self.assertRaises(ValueError):
            self.harness.charm.RouterRequirer.request_network(network_request)

        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_given_requirer_when_request_new_network_with_unreachable_route_then_raises_exception(
        self,
    ):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        existing_network = {"host-a": {"network": "192.168.252.0/24", "gateway": "192.168.252.1"}}
        self.harness.update_relation_data(
            rel_id, "ip-router-provider", {"networks": json.dumps(existing_network)}
        )

        network_request = {
            "host-b": {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.240.3"}],
            }
        }
        with self.assertRaises(ValueError):
            self.harness.charm.RouterRequirer.request_network(network_request)
        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_given_requirer_when_request_multiple_new_network_with_one_invalid_then_raises_exception(
        self,
    ):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        existing_network = {"host-a": {"network": "192.168.252.0/24", "gateway": "192.168.252.1"}}
        self.harness.update_relation_data(
            rel_id, "ip-router-provider", {"networks": json.dumps(existing_network)}
        )

        network_request = {
            "host-b": {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.240.3"}],
            },
            "host-c": {
                "network": "192.168.251.0/24",
                "gateway": "192.168.251.1",
            },
        }
        with self.assertRaises(ValueError):
            self.harness.charm.RouterRequirer.request_network(network_request)
        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_given_requirer_when_request_new_network_no_gateway_then_raises_exception(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        network_request = {
            "host-a": {"network": "192.168.240.0/20", "sad": "192.168.250.1"},
        }
        with self.assertRaises(KeyError):
            self.harness.charm.RouterRequirer.request_network(network_request)

        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_given_requirer_when_request_new_network_no_network_then_raises_exception(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        network_request = {
            "host-a": {"sad": "192.168.240.0/20", "gateway": "192.168.250.1"},
        }
        with self.assertRaises(KeyError):
            self.harness.charm.RouterRequirer.request_network(network_request)

        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_given_requirer_when_request_new_network_no_route_destination_then_raises_exception(
        self,
    ):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        network_request = {
            "host-a": {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destinope": "172.250.0.0/16", "gateway": "192.168.240.3"}],
            }
        }
        with self.assertRaises(KeyError):
            self.harness.charm.RouterRequirer.request_network(network_request)

        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {}

    def test_given_requirer_when_request_new_network_no_route_gateway_then_raises_exception(self):
        rel_id = self.harness.add_relation(IP_ROUTER_REQUIRER_RELATION_NAME, "ip-router-provider")
        self.harness.add_relation_unit(rel_id, "ip-router-provider/0")

        network_request = {
            "host-a": {
                "network": "192.168.250.0/24",
                "gateway": "192.168.250.1",
                "routes": [{"destination": "172.250.0.0/16", "gateroad": "192.168.240.3"}],
            }
        }
        with self.assertRaises(KeyError):
            self.harness.charm.RouterRequirer.request_network(network_request)
        assert self.harness.get_relation_data(rel_id, "ip-router-requirer") == {}
