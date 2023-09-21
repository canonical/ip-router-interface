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

import logging, json
from ipaddress import IPv4Interface, IPv4Network, IPv4Address

import ops

from charms.ip_router_interface.v0.ip_router_interface import *

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class SimpleIPRouteRequirerCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.RouterRequirer = RouterRequires(charm=self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.ip_router_relation_joined, self._on_relation_joined)

        self.framework.observe(self.on.get_routing_table_action, self._action_get_routing_table)
        self.framework.observe(self.on.request_network_action, self._action_request_network)

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.BlockedStatus("Waiting for relation to be created")

    def _on_relation_joined(self, event: ops.RelationJoinedEvent):
        self.unit.status = ops.ActiveStatus("Ready to Require")

    def _action_get_routing_table(self, event: ops.ActionEvent):
        rt = self.RouterRequirer.get_routing_table()
        event.set_results({"msg": json.dumps(rt)})

    def _action_request_network(self, event: ops.ActionEvent):
        self.RouterRequirer.request_network(json.loads(event.params["network"]))
        event.set_results({"msg": "ok"})


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(SimpleIPRouteRequirerCharm)  # type: ignore
