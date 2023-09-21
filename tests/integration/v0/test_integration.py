#!/usr/bin/env python3
# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.

import json
import logging
import os
import shutil

import pytest

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


async def validate_routing_table(unit, expected_rt) -> None:
    action = await unit.run_action(action_name="get-routing-table")
    action_output = await ops_test.model.get_action_output(  # noqa
        action_uuid=action.entity_id, wait=60
    )
    assert json.loads(action_output["msg"]) == expected_rt


class TestIntegration:
    requirer_charm = None
    provider_charm = None

    @pytest.mark.abort_on_fail
    async def test_given_charms_packed_when_deploy_charm_then_status_is_blocked(self, ops_test):
        copy_lib_content()
        TestIntegration.requirer_charm = await ops_test.build_charm(f"{REQUIRER_CHARM_DIR}/")
        TestIntegration.provider_charm = await ops_test.build_charm(f"{PROVIDER_CHARM_DIR}/")
        await ops_test.model.deploy(
            TestIntegration.provider_charm,
            application_name=IP_ROUTER_PROVIDER_APP_NAME,
            series="jammy",
        )
        await ops_test.model.deploy(
            TestIntegration.requirer_charm,
            application_name=f"{IP_ROUTER_REQUIRER_APP_NAME}-a",
            series="jammy",
        )
        await ops_test.model.wait_for_idle(
            apps=[f"{IP_ROUTER_REQUIRER_APP_NAME}-a", IP_ROUTER_PROVIDER_APP_NAME],
            status="blocked",
            timeout=1000,
        )

    @pytest.mark.abort_on_fail
    async def test_given_charms_deployed_when_relate_then_status_is_active(self, ops_test):
        await ops_test.model.add_relation(
            relation1=f"{IP_ROUTER_REQUIRER_APP_NAME}-a",
            relation2=IP_ROUTER_PROVIDER_APP_NAME,
        )

        await ops_test.model.wait_for_idle(
            apps=[f"{IP_ROUTER_REQUIRER_APP_NAME}-a", IP_ROUTER_PROVIDER_APP_NAME],
            status="active",
            timeout=1000,
        )

        # Check that the router has the correct app name in the routing table
        provider_unit = ops_test.model.units[f"{IP_ROUTER_PROVIDER_APP_NAME}/0"]

        action = await provider_unit.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == {f"{IP_ROUTER_REQUIRER_APP_NAME}-a": []}

    @pytest.mark.abort_on_fail
    async def test_given_network_request_provider_implements_and_requirer_sees(self, ops_test):
        # This emits an event called new_network_request
        provider_unit = ops_test.model.units[f"{IP_ROUTER_PROVIDER_APP_NAME}/0"]
        requirer_unit = ops_test.model.units[f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0"]

        # Run a "request-network" action on the requirer charm
        requested_network = [{"network": "192.168.250.0/24", "gateway": "192.168.250.1"}]
        action = await requirer_unit.run_action(
            action_name="request-network", network=json.dumps(requested_network)
        )
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert action_output["msg"] == "ok"

        # Wait for the model to finish executing `relation-changed`
        await ops_test.model.wait_for_idle(
            apps=[f"{IP_ROUTER_REQUIRER_APP_NAME}-a", IP_ROUTER_PROVIDER_APP_NAME],
            status="active",
            timeout=1000,
        )

        # Run a "get-routing-table" action on the provider charm
        provider_unit = ops_test.model.units[f"{IP_ROUTER_PROVIDER_APP_NAME}/0"]
        action = await provider_unit.run_action(action_name="get-flattened-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == requested_network

    @pytest.mark.abort_on_fail
    async def test_full_end2end_test(self, ops_test):
        # Deploy and relate another requirer
        await ops_test.model.deploy(
            TestIntegration.requirer_charm,
            application_name=f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
            series="jammy",
        )
        await ops_test.model.wait_for_idle(
            apps=[f"{IP_ROUTER_REQUIRER_APP_NAME}-b"],
            status="blocked",
            timeout=1000,
        )
        await ops_test.model.add_relation(
            relation1=f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
            relation2=IP_ROUTER_PROVIDER_APP_NAME,
        )
        await ops_test.model.wait_for_idle(
            apps=[
                f"{IP_ROUTER_REQUIRER_APP_NAME}-a",
                f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
                IP_ROUTER_PROVIDER_APP_NAME,
            ],
            status="active",
            timeout=1000,
        )
        provider_unit = ops_test.model.units[f"{IP_ROUTER_PROVIDER_APP_NAME}/0"]
        action = await provider_unit.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == {
            "ip-router-requirer-a": json.dumps(
                [{"network": "192.168.250.0/24", "gateway": "192.168.250.1"}]
            ),
            "ip-router-requirer-b": [],
        }

        requirer_unit_1 = ops_test.model.units[f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0"]
        requirer_unit_2 = ops_test.model.units[f"{IP_ROUTER_REQUIRER_APP_NAME}-b/0"]

        # requirer1 sends a network request
        requested_network = [{"network": "192.168.251.0/24", "gateway": "192.168.251.1"}]
        action = await requirer_unit_1.run_action(
            action_name="request-network", network=json.dumps(requested_network)
        )

        # Wait for all apps to be done
        await ops_test.model.wait_for_idle(
            apps=[
                f"{IP_ROUTER_REQUIRER_APP_NAME}-a",
                f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
                IP_ROUTER_PROVIDER_APP_NAME,
            ],
            status="active",
            timeout=1000,
        )

        # assert there is a new network in all charms
        expected_flat_table = [
            {"network": "192.168.251.0/24", "gateway": "192.168.251.1"},
        ]
        expected_rt = {
            "ip-router-requirer-a": json.dumps(
                [{"network": "192.168.251.0/24", "gateway": "192.168.251.1"}]
            ),
            "ip-router-requirer-b": [],
        }

        action = await provider_unit.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == expected_rt
        action = await requirer_unit_1.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == expected_flat_table
        action = await requirer_unit_2.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == expected_flat_table

        # requirer2 sends a network request
        requested_network = [{"network": "192.168.252.0/24", "gateway": "192.168.252.1"}]
        action = await requirer_unit_2.run_action(
            action_name="request-network", network=json.dumps(requested_network)
        )

        # Wait for all apps to be done
        await ops_test.model.wait_for_idle(
            apps=[
                f"{IP_ROUTER_REQUIRER_APP_NAME}-a",
                f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
                IP_ROUTER_PROVIDER_APP_NAME,
            ],
            status="active",
            timeout=1000,
        )

        expected_flat_table = [
            {"network": "192.168.251.0/24", "gateway": "192.168.251.1"},
            {"network": "192.168.252.0/24", "gateway": "192.168.252.1"},
        ]
        expected_rt = {
            "ip-router-requirer-a": json.dumps(
                [{"network": "192.168.251.0/24", "gateway": "192.168.251.1"}]
            ),
            "ip-router-requirer-b": json.dumps(
                [{"network": "192.168.252.0/24", "gateway": "192.168.252.1"}]
            ),
        }

        action = await provider_unit.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == expected_rt
        action = await requirer_unit_1.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == expected_flat_table
        action = await requirer_unit_2.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == expected_flat_table
