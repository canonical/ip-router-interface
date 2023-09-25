# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Library for the ip-router integration

This library contains the Requires and Provides classes for interactions through the 
ip-router interface

## Getting Started

From a charm directory, fetch the library using `charmcraft`:

```shell
charmcraft fetch-lib charms.ip_router_interface.v0.ip_router_interface
```

### Provider charm
This example provider charm is all we need to listen to ip-router requirer requests.
The ip-router provider fulfills the routing function for multiple charms that are
requirers of the ip-router interface. For that reason, this charm will continuously
track and update all of the connected requirers and the networks and routes they've 
requested, which it does in a routing table. As new charms are connected and disconnected
to the relation, this routing table is automatically adds and removes the dependent
networks.

The library handles the listening and synchronization for all of the ip-router network
requests internally, which means as the charm author you don't need to worry about any
of the business logic of validating or orchestrating the relation network.

You can also listen to the `routing_table_updated` event for convenience.


```python
import logging, json
import ops
from charms.ip_router_interface.v0.ip_router_interface import *

class SimpleIPRouteProviderCharm(ops.CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.RouterProvider = RouterProvides(charm=self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.routing_table_updated, self._routing_table_updated)
        self.framework.observe(self.on.get_routing_table_action, self._action_get_routing_table)

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.ActiveStatus("Ready to Provide")

    def _routing_table_updated(self, event: RoutingTableUpdatedEvent):
        routing_table = self.RouterProvider.get_routing_table()
        all_networks = self.RouterProvider.get_flattened_routing_table()

        # Process the networks however you like
        implement_networks(all_networks)
        
        
    def _action_get_routing_table(self, event: ops.ActionEvent):
        all_networks = self.RouterProvider.get_flattened_routing_table()
        event.set_results({"msg": json.dumps(all_networks)})
    


if __name__ == "__main__":  # pragma: nocover
    ops.main(SimpleIPRouteProviderCharm)  # type: ignore
```

### Requirer charm
This example requirer charm shows the two available actions as a host in the network:
* get the latest list of all networks available from the provider
* request a network to be assigned to the requirer charm

The ip-router requirer allows a foolproof, typechecked, secure and safe way to 
interact with the router that handles validation and format of the network 
request, so you can focus on more important things. The library also provides a
way to list out all of the available networks. This list is not cached, and comes
directly from the provider.

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

        self.framework.observe(self.on.get_all_networks_action, self._action_get_all_networks)
        self.framework.observe(self.on.request_network_action, self._action_request_network)

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.ActiveStatus("Ready to Provide")

    def _on_relation_joined(self, event: ops.RelationJoinedEvent):
        self.unit.status = ops.ActiveStatus("Ready to Require")

    def _action_get_all_networks(self, event: ops.ActionEvent):
        # Get and process all of the available networks
        all_networks = self.RouterRequirer.get_all_networks()
        event.set_results({"msg": json.dumps(all_networks)})

    def _action_request_network(self, event: ops.ActionEvent):
        # Request a new network as required in the required format
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
LIBPATCH = 2

from ipaddress import IPv4Address, IPv4Network
from copy import deepcopy
from typing import Dict, List, Union, TypeAlias
from ops.framework import Object, EventSource, EventBase, ObjectEvents
from ops.charm import CharmBase
from ops import RelationJoinedEvent, RelationChangedEvent, RelationDepartedEvent, StoredState
import logging, json

logger = logging.getLogger(__name__)

Network: TypeAlias = Dict[
    str,  # 'network' | 'gateway' | 'routes'
    Union[
        IPv4Address,  # gateway, ex: '192.168.250.1'
        IPv4Network,  # network, ex: '192.168.250.0/24'
        List[  # List of routes
            Dict[
                str,  # 'destination' | 'gateway'
                Union[
                    IPv4Address,  # gateway, ex: '192.168.250.3'
                    IPv4Network,  # destination, ex: '172.250.0.0/16'
                ],
            ]
        ],
    ],
]

RoutingTable: TypeAlias = Dict[
    str,  # Name of the application
    List[Network],  # All networks for this application
]


class RoutingTableUpdatedEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """


class RouterProviderCharmEvents(ObjectEvents):
    routing_table_updated = EventSource(RoutingTableUpdatedEvent)


class RouterProvides(Object):
    """This class is used to manage the routing table of the router provider.

    It's capabilities are to:
    * Manage the routing table in the charm itself, by adding and removing
    new network and route requests by integrated units,
    * Synchronize the databags of all requiring units with the router table of the
    provider charm

    Attributes:
        charm:
            The Charm object that instantiates this class
        _stored:
            The persistent state that keeps the internal routing table.
    """

    on = RouterProviderCharmEvents()
    _stored = StoredState()

    def __init__(self, charm: CharmBase, relationship_name: str = "ip-router"):
        super().__init__(charm, relationship_name)
        self.charm = charm
        self.relationship_name = relationship_name
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
        self._stored.routing_table.update({event.relation.app.name: []})
        self._sync_routing_tables()

    def _on_ip_router_relation_changed(self, event: RelationChangedEvent):
        """Update the internal routing table state to reflect changes in
        requirer units' new network requests.
        """
        if not self.charm.unit.is_leader():
            return

        if "networks" not in event.relation.data[event.relation.app]:
            return

        new_network = event.relation.data[event.relation.app]["networks"]
        if new_network == self._stored.routing_table[event.relation.app.name]:
            return
        self._stored.routing_table[event.relation.app.name] = new_network
        self._sync_routing_tables()
        self.on.routing_table_updated.emit()

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
        internal_routing_table = self.get_routing_table()
        final_routing_table = []
        for networks in internal_routing_table.values():
            if isinstance(networks, str):
                continue
            for network in json.loads(networks):
                final_routing_table.append(network)

        return final_routing_table

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

    def __init__(self, charm: CharmBase, relationship_name: str = "ip-router"):
        super().__init__(charm, relationship_name)
        self.charm = charm
        self.relationship_name = relationship_name

    def request_network(
        self,
        networks: List[Network],
    ) -> None:
        """Requests a new network interface from the ip-router provider

        The interfaces must be valid according to `_network_is_valid`. Multiple
        calls to this function will replace the previously requested networks,
        so all of the networks required must be given with each call.

        Arguments:
            networks:
                A list containing the desired networks of the type `Network`.

        Raises:
            RuntimeError:
                No ip-router relation exists yet or validation of one
            or more of the networks failed.
        """
        if not self.charm.unit.is_leader():
            return

        ip_router_relations = self.model.relations.get(self.relationship_name)
        if len(ip_router_relations) == 0:
            raise RuntimeError("No ip-router relation exists yet.")

        for network_request in networks:
            self._validate_network(network_request, networks)

        # Place it in the databags
        for relation in ip_router_relations:
            relation.data[self.charm.app].update({"networks": json.dumps(networks)})

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

    def _validate_network(self, network_request: Network, new_networks: List[Network]) -> bool:
        """Validates the network configuration created by the ip-router requirer

        The requested network must have all of the required fields, the gateway
        has to be located within the network, and all of the routes need to have
        a path through the top level network. The requested network must also be
        unassigned by the provider.

        Args:
            network_request:
                An object of type `Network` that will be validated.
            new_networks:
                The rest of the networks to check if this one is mutually
                exclusive to the rest of the subnets.

        Raises:
            ValueError:
                Reasons could be that the gateway is not within the network,
                there is no route to the destination, the network is already
                taken or the same network is requested twice.
            KeyError:
                Missing required key
        """
        if "gateway" not in network_request:
            raise KeyError("Key 'gateway' not found.")

        if "network" not in network_request:
            raise KeyError("Key 'network' not found.")

        gateway = IPv4Address(network_request.get("gateway"))
        network = IPv4Network(network_request.get("network"))

        if gateway not in network:
            ValueError("Chosen gateway not within given network.")

        for route in network_request.get("routes", []):
            if "gateway" not in route:
                raise KeyError("Key 'gateway' not found in route.")

            if "destination" not in route:
                raise KeyError("Key 'destination' not found in route.")
            route_gateway = IPv4Address(route["gateway"])
            if route_gateway not in network:
                raise ValueError("There is no route to this destination from the network.")

        for entry in new_networks:
            if entry == network_request:
                continue
            existing_network = IPv4Network(entry["network"])
            new_network = IPv4Network(network_request["network"])

            if new_network.subnet_of(existing_network) or new_network.supernet_of(
                existing_network
            ):
                raise ValueError("This network has been defined in another entry.")

        routing_table = self.get_all_networks()
        for entry in routing_table:
            existing_network = IPv4Network(entry["network"])
            new_network = IPv4Network(network_request["network"])

            if new_network.subnet_of(existing_network) or new_network.supernet_of(
                existing_network
            ):
                raise ValueError("This network is already taken by another requirer.")
