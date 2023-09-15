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
        self.framework.observe(self.on.request_route_action, self._action_request_route)

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.BlockedStatus("Waiting for relation to be created")

    def _on_relation_joined(self, event: ops.RelationJoinedEvent):
        self.unit.status = ops.ActiveStatus("Ready to Require")

    def _action_get_routing_table(self, event: ops.ActionEvent):
        rt = self.RouterRequirer.get_routing_table()
        event.set_results({"msg": json.dumps(rt)})

    def _action_request_network(self, event: ops.ActionEvent):
        self.RouterRequirer.request_network(IPv4Interface(event.params["network"]))
        event.set_results({"message": "ok"})

    def _action_request_route(self, event: ops.ActionEvent):
        network = IPv4Address(event.params["network"])
        destination = IPv4Network(event.params["destination"])
        gateway = IPv4Address(event.params["gateway"])

        self.RouterRequirer.request_route(
            existing_network=IPv4Address(network),
            destination=IPv4Network(destination),
            gateway=IPv4Address(gateway),
        )

        event.set_results({"message": "ok"})


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(SimpleIPRouteRequirerCharm)  # type: ignore
