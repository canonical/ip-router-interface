# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

"""Library for the ip-router integration

This library contains ther Requires and Provides classes for interactions through the 
ip-router interface

## Getting Started

From a charm directory, fetch the library using `charmcraft`:

```shell
charmcraft fetch-lib charms.ip_router_interface.v0.ip_router_interface TODO: Verify this works
```

### Provider charm
This example provider charm is all we need to listen to ip-router requirer requests:

```python
import logging, json
import ops
from charms.ip_router_interface.v0.ip_router_interface import *

class SimpleIPRouteProviderCharm(ops.CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.RouterProvider = RouterProvides(charm=self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.ip_router_relation_joined, self._on_relation_joined)

    def _on_install(self, event: ops.InstallEvent):
        pass

    def _on_relation_joined(self, event: ops.RelationJoinedEvent):
        self.unit.status = ops.ActiveStatus("Ready to Provide")


if __name__ == "__main__":  # pragma: nocover
    ops.main(SimpleIPRouteProviderCharm)  # type: ignore
```

### Requirer charm
This example requirer charm shows a flow where the user can run actions to request
new networks and get the available networks:

```python
import logging, json
import ops

from charms.ip_router_interface.v0.ip_router_interface import *

class SimpleIPRouteRequirerCharm(ops.CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.RouterRequirer = RouterRequires(charm=self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.ip_router_relation_joined, self._on_relation_joined)

        self.framework.observe(self.on.get_routing_table_action, self._action_get_routing_table)
        self.framework.observe(self.on.request_network_action, self._action_request_network)

    def _on_install(self, event: ops.InstallEvent):
        pass

    def _on_relation_joined(self, event: ops.RelationJoinedEvent):
        self.unit.status = ops.ActiveStatus("Ready to Require")

    def _action_get_routing_table(self, event: ops.ActionEvent):
        rt = self.RouterRequirer.get_routing_table()
        event.set_results({"msg": json.dumps(rt)})

    def _action_request_network(self, event: ops.ActionEvent):
        self.RouterRequirer.request_network(event.params["network"])
        event.set_results({"msg": "ok"})


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(SimpleIPRouteRequirerCharm)  # type: ignore
```

You can relate both charms by running:

```bash
juju integrate <ip-router provider charm> <ip-router requirer charm>
```
"""  # noqa: D405, D410, D411, D214, D416

# The unique Charmhub library identifier, never change it
LIBID = "8bed752769244d9ba01c61d5647683cf"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

from ipaddress import IPv4Address, IPv4Network
from copy import deepcopy
from typing import Dict, List, Union
from ops.framework import EventBase, Object, EventSource, ObjectEvents
from ops.charm import CharmBase
from ops import RelationJoinedEvent, RelationChangedEvent, RelationDepartedEvent, StoredState
import logging, json


logger = logging.getLogger(__name__)

Network = Dict[
    str,  # 'network' | 'gateway' | 'routes'
    Union[
        IPv4Address,  # gateway, ex: '192.168.250.1'
        IPv4Network,  # network, ex: '192.168.250.0/24'
        List[  # List of routes
            Dict[
                str,  # 'destination' | 'gateway'
                Union[
                    IPv4Address,  # gateway, ex: '192.168.250.3'
                    IPv4Network,  # destionation, ex: '172.250.0.0/16'
                ],
            ]
        ],
    ],
]

RoutingTable = Dict[
    str,  # Name of the application
    List[Network],  # All networks for this application
]


class RoutingTableUpdatedEvent(EventBase):
    """
    Charm event for when the network routing table changes.
    """


class NewNetworkRequestEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """


class NewRouteRequestEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """


class RouterProviderCharmEvents(ObjectEvents):
    new_network_request = EventSource(NewNetworkRequestEvent)
    new_route_request = EventSource(NewRouteRequestEvent)
    routing_table_updated = EventSource(RoutingTableUpdatedEvent)


class RouterRequirerCharmEvents(ObjectEvents):
    new_network_request = EventSource(NewNetworkRequestEvent)
    new_route_request = EventSource(NewRouteRequestEvent)
    routing_table_updated = EventSource(RoutingTableUpdatedEvent)


class RouterProvides(Object):
    """This class is used to manage the routing table of the router provider.

    It's capabilities are to:
    * Manage the routing table in the charm itself, by adding and removing
    new network and route requests by integrated units,
    * Syncronize the databags of all requiring units with the router table of the
    provider charm

    Attributes:
        charm: The Charm object that instantiates this class
        _stored: The persistent state that keeps the internal routing table.
    """

    _stored = StoredState()
    on = RouterProviderCharmEvents()

    def __init__(self, charm: CharmBase):
        super().__init__(charm, "ip-router")
        self.charm = charm
        self._stored.set_default(routing_table={})
        self.framework.observe(
            charm.on.ip_router_relation_changed, self._on_ip_router_relation_changed
        )
        self.framework.observe(
            charm.on.ip_router_relation_joined, self._on_ip_router_relation_joined
        )
        self.framework.observe(
            charm.on.ip_router_relation_departed, self._on_ip_router_relation_departed
        )

    def _on_ip_router_relation_joined(self, event: RelationJoinedEvent):
        """When a new unit or app joins the relation, add its name to the routing table"""
        self._stored.routing_table.update({event.relation.app.name: {"networks": []}})
        self._sync_routing_tables()

    def _on_ip_router_relation_changed(self, event: RelationChangedEvent):
        """Update the internal routing table state to reflect changes in
        requirer units' new network requests.
        """
        if not self.charm.unit.is_leader():
            return

        new_network = event.relation.data[event.relation.app]["networks"]
        self._stored.routing_table[event.relation.app.name] = new_network
        self._sync_routing_tables()

    def _on_ip_router_relation_departed(self, event: RelationDepartedEvent):
        """If an application has completely departed the relation, remove it
        from the routing table.
        """
        if len(event.relation.units) == 0:
            self._stored.routing_table.pop(event.app.name)
            self._sync_routing_tables()

    def get_routing_table(self) -> RoutingTable:
        """Read-only way to get the current routing table"""
        return deepcopy(self._stored.routing_table._under)  # RFC: Is there a better way?

    def get_flattened_routing_table(self) -> List[Network]:
        """Returns a read-only internal routing table that's flattened

        Returns:
            A list of objects of type `Network`
        """
        internal_rt = self.get_routing_table()
        final_rt = []
        for networks in internal_rt.values():
            if type(networks) is not str:
                continue
            for network in json.loads(networks):
                final_rt.append(network)

        return final_rt

    def _sync_routing_tables(self) -> None:
        """Syncs the internal routing table with all of the requirer's app databags"""
        ip_router_relations = self.model.relations["ip-router"]
        for relation in ip_router_relations:
            relation.data[self.charm.app].update(
                {"networks": json.dumps(self.get_flattened_routing_table())}
            )


class RouterRequires(Object):
    """ip-router requirer class to be instantiated by charms that require routing

    This class provides methods to request a new network, and read the available
    network from the router providers. These should be used exclusively to
    interact with the relation.

    Attributes:
        charm: The Charm object that instantiates this class.
    """

    on = RouterRequirerCharmEvents()  # RFC: Is this actually needed?

    def __init__(self, charm: CharmBase):
        super().__init__(charm, "ip-router")
        self.charm = charm

    def request_network(
        self,
        networks: List[Network],
    ) -> None:
        """Requests a new network interface from all of the ip-router providers

        The interfaces must be valid according to `_network_is_valid`. Multiple
        calls to this function will replace the previously requested networks,
        so all of the networks required must be given with each call.

        Arguments:
            networks: A list containing the desired networks of the type `Network`.

        Raises:
            RFC: ValueError, KeyError etc. copy over the _network_is_valid function errors?
        """
        if not self.charm.unit.is_leader():
            return

        valid_requests = []
        for network_request in networks:
            if self._network_is_valid(network_request):
                valid_requests.append(
                    network_request
                )  # RFC: Should we add valid ones or reject everything if only some are invalid?

        # Place it in the databags if they exist
        for relation in self.model.relations.get("ip-router"):
            relation.data[self.charm.app].update({"networks": json.dumps(valid_requests)})

    def get_all_networks(self) -> List[Network]:
        """Fetches combined routing tables made available by ip-router providers

        Args:
            None
        Returns:
            A list of objects of type `Network`. This list contains networks
            from all ip-router providers that are integrated with the charm.
        """
        if not self.charm.unit.is_leader():
            return

        router_relations = self.model.relations.get("ip-router")

        all_networks = []
        for relation in router_relations:
            if networks := relation.data[relation.app].get("networks"):
                all_networks.extend(json.loads(networks))
        return all_networks

    def _network_is_valid(self, network_request: Network) -> bool:
        """Validates the network configuration created by the ip-router requirer

        The requested network must have all of the required fields, the gateway
        has to be located within the network, and all of the routes need to have
        a path through the top level network. The requested network must also be
        unassigned by the provider.

        Args:
            network_request: An object of type `Network`.

        Returns:
            True if network is valid, False if not.

        Raises:
            ValueError: Value wrong
            KeyError: Missing key somewhere
            RFC: Decide on if we should raise something here.
            It honestly makes sense because we don't want to have an invalid state ever
        """
        if "gateway" not in network_request:
            logger.error("Key 'gateway' not found. Skipping entry.")
            return False

        if "network" not in network_request:
            logger.error("Key 'network' not found. Skipping entry.")
            return False

        gateway = IPv4Address(network_request.get("gateway"))
        network = IPv4Network(network_request.get("network"))

        if gateway not in network:
            logger.error("Chosen gateway not within given network. Skipping entry.")
            return False

        for route in network_request.get("routes", []):
            if "gateway" not in route:
                logger.error("Key 'gateway' not found in route. Skipping entry")
                return False

            if "destination" not in route:
                logger.error("Key 'destination' not found in route. Skipping entry")
                return False
            route_gateway = IPv4Address(route["gateway"])
            if route_gateway not in network:
                logger.error("There is no route to this destination from the network.")
                return False

        rt = self.get_all_networks()
        for entry in rt:
            existing_network = IPv4Network(entry["network"])
            new_network = IPv4Network(network_request["network"])

            if new_network.subnet_of(existing_network) or new_network.supernet_of(
                existing_network
            ):
                logger.error("This network is already taken.")
                return False

        return True
