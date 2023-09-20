#!/usr/bin/env python3
# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.

import logging, shutil, pytest, os, json
from time import sleep

from pytest_operator.plugin import OpsTest

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
    action_output = await ops_test.model.get_action_output(action_uuid=action.entity_id, wait=60)
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
        assert json.loads(action_output["msg"]) == {
            f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0": {"networks": []}
        }

    @pytest.mark.abort_on_fail
    async def test_given_network_request_provider_implements_and_requirer_sees(self, ops_test):
        # This emits an event called new_network_request
        provider_unit = ops_test.model.units[f"{IP_ROUTER_PROVIDER_APP_NAME}/0"]
        requirer_unit = ops_test.model.units[f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0"]

        # Run a "request-network" action on the requirer charm
        action = await requirer_unit.run_action(
            action_name="request-network", network="192.168.250.1/24"
        )
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert action_output["msg"] == "ok"

        # Sleep a minute to make sure the action has ran on both sides
        sleep(120)

        # Run a "get-routing-table" action on the provider charm
        provider_unit = ops_test.model.units[f"{IP_ROUTER_PROVIDER_APP_NAME}/0"]
        action = await provider_unit.run_action(action_name="get-routing-table")
        action_output = await ops_test.model.get_action_output(
            action_uuid=action.entity_id, wait=60
        )
        assert json.loads(action_output["msg"]) == {
            f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0": {
                "networks": [{"network": "192.168.250.0/24", "gateway": "192.168.250.1"}]
            },
        }

    # @pytest.mark.abort_on_fail
    # async def test_full_end2end_test(self, ops_test):
    #     # Deploy and relate another requirer
    #     await ops_test.model.deploy(
    #         TestIntegration.requirer_charm,
    #         application_name=f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
    #         series="jammy",
    #     )
    #     await ops_test.model.wait_for_idle(
    #         apps=[f"{IP_ROUTER_REQUIRER_APP_NAME}-b"],
    #         status="blocked",
    #         timeout=1000,
    #     )
    #     await ops_test.model.add_relation(
    #         relation1=f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
    #         relation2=IP_ROUTER_PROVIDER_APP_NAME,
    #     )
    #     await ops_test.model.wait_for_idle(
    #         apps=[
    #             f"{IP_ROUTER_REQUIRER_APP_NAME}-a",
    #             f"{IP_ROUTER_REQUIRER_APP_NAME}-b",
    #             IP_ROUTER_PROVIDER_APP_NAME,
    #         ],
    #         status="active",
    #         timeout=1000,
    #     )
    #     provider_unit = ops_test.model.units[f"{IP_ROUTER_PROVIDER_APP_NAME}/0"]
    #     action = await provider_unit.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == {
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0": {},
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-b/0": {},
    #     }

    #     requirer_unit_1 = ops_test.model.units[f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0"]
    #     requirer_unit_2 = ops_test.model.units[f"{IP_ROUTER_REQUIRER_APP_NAME}-b/0"]

    #     # requirer1 sends a network request
    #     action = await requirer_unit_1.run_action(
    #         action_name="request-network", network="192.168.250.1/24"
    #     )

    #     # assert there is a new network in all charms
    #     expected_rt = {
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0": {
    #             "networks": [{"network": "192.168.250.0/24", "gateway": "192.168.250.1"}],
    #         },
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-b/0": {},
    #     }

    #     action = await provider_unit.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt
    #     action = await requirer_unit_1.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt
    #     action = await requirer_unit_2.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt

    #     # requirer1 sends a route request
    #     action = await requirer_unit_1.run_action(
    #         action_name="request-route",
    #         network="192.168.250.1/24",
    #         destination="172.250.0.0/16",
    #         gateway="192.168.250.3",
    #     )

    #     expected_rt = {
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0": {
    #             "networks": [
    #                 {
    #                     "network": "192.168.250.0/24",
    #                     "gateway": "192.168.250.1",
    #                     "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
    #                 },
    #                 {
    #                     "network": "192.168.252.0/24",
    #                     "gateway": "192.168.252.1",
    #                 },
    #             ],
    #         },
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-b/0": {},
    #     }

    #     action = await provider_unit.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt
    #     action = await requirer_unit_1.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt
    #     action = await requirer_unit_2.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt

    #     # requirer2 sends a network request
    #     action = await requirer_unit_2.run_action(
    #         action_name="request-network", network_request="192.168.252.1/24"
    #     )

    #     expected_rt = {
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-a/0": {
    #             "networks": [
    #                 {
    #                     "network": "192.168.250.0/24",
    #                     "gateway": "192.168.250.1",
    #                     "routes": [{"destination": "172.250.0.0/16", "gateway": "192.168.250.3"}],
    #                 }
    #             ],
    #         },
    #         f"{IP_ROUTER_REQUIRER_APP_NAME}-b/0": {
    #             "networks": [
    #                 {
    #                     "network": "192.168.252.0/24",
    #                     "gateway": "192.168.252.1",
    #                 }
    #             ]
    #         },
    #     }

    #     action = await provider_unit.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt
    #     action = await requirer_unit_1.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt
    #     action = await requirer_unit_2.run_action(action_name="get-routing-table")
    #     action_output = await ops_test.model.get_action_output(
    #         action_uuid=action.entity_id, wait=60
    #     )
    #     assert json.loads(action_output["msg"]) == expected_rt

    # remove requirer1 from relation

    # assert requirer1 is gone from the storedstate rt
    # assert requirer 2 no longer has the route in its databag

    # assert 1 == 1
    # pass
