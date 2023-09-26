#!/usr/bin/env python3
# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
"""

import json
import logging

import ops
from charms.ip_router_interface.v0.ip_router_interface import RouterProvides  # noqa

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]

IP_ROUTER_PROVIDER_RELATION_NAME = "example-router"


class SimpleIPRouteProviderCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.RouterProvider = RouterProvides(
            charm=self, relationship_name=IP_ROUTER_PROVIDER_RELATION_NAME
        )  # noqa
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(
            self.on[IP_ROUTER_PROVIDER_RELATION_NAME].relation_joined, self._on_relation_joined
        )
        self.framework.observe(self.on.get_routing_table_action, self._action_get_routing_table)
        self.framework.observe(
            self.on.get_flattened_routing_table_action, self._action_get_flattened_routing_table
        )

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.BlockedStatus("Waiting for relation to be created")

    def _on_relation_joined(self, event: ops.RelationJoinedEvent):
        self.unit.status = ops.ActiveStatus("Ready to Provide")

    def _action_get_routing_table(self, event: ops.ActionEvent):
        rt = self.RouterProvider.get_routing_table()
        event.set_results({"msg": json.dumps(rt)})

    def _action_get_flattened_routing_table(self, event: ops.ActionEvent):
        rt = self.RouterProvider.get_flattened_routing_table()
        event.set_results({"msg": json.dumps(rt)})


if __name__ == "__main__":
    ops.main.main(SimpleIPRouteProviderCharm)
