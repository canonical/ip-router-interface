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
This example provider charm shows how the library could be utilized to provide
ip routing functionality. From the point of view of the provider charm, it's possible to:

* Return the live routing table,
* Observe whenever the routing table is updated

The library itself takes care of adding, removing, updating the networks requested,
and the synchronization of the routing table between the requirers,
which means as the author of the provider charm, there is no need to handle the 
logic of the objects of type Network. 

When reading the routing table directly, the following are guaranteed by the 
library:

* The networks that are available in the routing table are:
    * Unique,
    * Valid as described by the function _validate_network,
    * Associated with a single requirer application

You can also listen to the `routing_table_updated` event that is emitted after all of
 the tables are synced, which guarantees that the routing table is updated at the moment.

```python
import logging, json
import ops
from charms.ip_router_interface.v0.ip_router_interface import RouterProvides

class SimpleIPRouteProviderCharm(ops.CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.RouterProvider = RouterProvides(charm=self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.RouterProvider.on.routing_table_updated, self._routing_table_updated)
        self.framework.observe(self.on.get_routing_table_action, self._action_get_routing_table)

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.ActiveStatus("Ready to Provide")

    def _routing_table_updated(self, event: RoutingTableUpdatedEvent):
        # The table can be used automatically after updating 
        routing_table = event.routing_table
        implement_networks(routing_table)
        
    def _action_get_routing_table(self, event: ops.ActionEvent):
        # The table can be used on-demand
        all_networks = self.RouterProvider.get_routing_table()
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
        self.framework.observe(self.RouterRequirer.on.routing_table_updated, self._routing_table_updated)

        self.framework.observe(self.on.get_all_networks_action, self._action_get_all_networks)
        self.framework.observe(self.on.request_network_action, self._action_request_network)

    def _on_install(self, event: ops.InstallEvent):
        self.unit.status = ops.ActiveStatus("Ready to Provide")

    def _on_relation_joined(self, event: ops.RelationJoinedEvent):
        self.unit.status = ops.ActiveStatus("Ready to Require")

    def _routing_table_updated(self, event: RoutingTableUpdatedEvent):
        # Get and process all of the available networks when they're updated
        all_networks = self.RouterRequirer.get_routing_table()

    def _action_get_all_networks(self, event: ops.ActionEvent):
        # Get and process all of the available networks any time you like
        all_networks = self.RouterRequirer.get_routing_table()
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
LIBPATCH = 3

from ipaddress import IPv4Address, IPv4Network
from typing import Dict, List, Union, TypeAlias
from ops.framework import Object, EventSource, EventBase, ObjectEvents
from ops.charm import CharmBase
from ops import RelationChangedEvent, RelationDepartedEvent, Relation
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

RoutingTable: TypeAlias = Dict[str, Network]  # Name of the network  # A Dict of type Network


class RoutingTableUpdatedEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """

    def __init__(self, handle, routing_table=None):
        super().__init__(handle)
        self.routing_table = routing_table

    def snapshot(self):
        return {"data": self.routing_table}

    def restore(self, snapshot):
        self.routing_table = snapshot["data"]


class RouterProviderCharmEvents(ObjectEvents):
    routing_table_updated = EventSource(RoutingTableUpdatedEvent)


class RouterRequirerCharmEvents(ObjectEvents):
    routing_table_updated = EventSource(RoutingTableUpdatedEvent)


def _validate_network(network_request: Network, existing_routing_table: RoutingTable):
    """Validates the network configuration created by the ip-router requirer

    The requested network must have all of the required keys as indicated in the
    Network type ('gateway' and 'network'), the gateway has to be located within
    the network, and all of the routes need to have a path through the top level
    network. The requested network must also be previously unassigned by the
    provider.

    Args:
        network_request:
            An object of type `Network` that will be validated.
        existing_routing_table:
            The existing routing table. The given network will be checked to see
            if it could be added to this object.

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

    for existing_network in existing_routing_table.values():
        old_subnet = IPv4Network(existing_network["network"])
        new_subnet = IPv4Network(network_request["network"])

        if old_subnet.subnet_of(new_subnet) or old_subnet.supernet_of(new_subnet):
            raise ValueError("This network has been defined in a previous entry.")


class RouterProvides(Object):
    """This class is initialized by the ip-router provider to automatically
    accept new network requests from ip-router requirers and synchronize all
    requirers' databags with the new network topology.

    It's capabilities are to:
    * Build a Routing Table from all of the databags of the requirers with their
    declared networks.
    * Synchronize the databags of all requiring units with the aforementioned
    routing table.
    * Send events indicating a change in this table.

    Attributes:
        charm:
            The Charm object that instantiates this class.
        relation_name:
            The name used for the relation implementing the ip-router interface.
            All requirers that integrate to this name are grouped into one routing table.
            "ip-router" by default.
    """

    on = RouterProviderCharmEvents()

    def __init__(self, charm: CharmBase, relation_name: str = "ip-router"):
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name
        self.framework.observe(
            charm.on[relation_name].relation_changed, self._router_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_departed, self._router_relation_departed
        )

    def _router_relation_changed(self, event: RelationChangedEvent):
        """Update and sync the routing tables when a databag changes."""
        if not self.charm.unit.is_leader():
            return
        self._sync_routing_tables()
        new_table = self.get_routing_table()
        self.on.routing_table_updated.emit({"networks": new_table})

    def _router_relation_departed(self, event: RelationDepartedEvent):
        """Update and sync the routing tables if an application leaves."""
        if not self.charm.unit.is_leader():
            return
        self._sync_routing_tables()
        new_table = self.get_routing_table()
        self.on.routing_table_updated.emit({"networks": new_table})

    def get_routing_table(self) -> RoutingTable:
        """Build the routing table by collecting network requests from all related
        requirer databags. If there are errors or invalid network definitions in
        the databags, they will be raised here, but must be fixed in the requirer
        charm.

        Raises:
            JSONDecodeError:
                The json from the databag was not decodable
            RuntimeError:
                There was an error with verifying the network request.
        """
        router_relations = self.model.relations[self.relation_name]
        final_routing_table: RoutingTable = {}

        for relation in router_relations:
            try:
                network_requests: RoutingTable = json.loads(
                    relation.data[relation.app].get("networks")
                )
            except json.decoder.JSONDecodeError as e:
                logger.error(
                    "Failed parsing JSON from app %s databag. Skipping all networks from this app. %s",
                    relation.app.name,
                    relation.data[relation.app],
                )
                continue
            except TypeError as e:
                continue

            for new_network_name, new_network in network_requests.items():
                if not new_network_name or not new_network:
                    continue
                if new_network_name in final_routing_table.keys():
                    error_string = (
                        "Duplicate network name %s detected at least from second application %s, probably due to a race condition. Please make sure your network names are unique between applications.",
                        new_network_name,
                        relation.app.name,
                    )
                    logger.error(error_string)
                    raise RuntimeError(error_string)

                try:
                    _validate_network(new_network, final_routing_table)
                except (ValueError, KeyError) as e:
                    error_string = (
                        "Exception (%s) occurred with network %s. This exception should be fixed at the requirer side.",
                        e.args[0],
                        new_network,
                    )
                    logger.error(error_string)
                    raise RuntimeError(error_string)
                else:
                    final_routing_table[new_network_name] = new_network
                    logger.debug(
                        "Added (%s) from app:(%s) with relation-name:(%s)",
                        new_network_name,
                        relation.app.name,
                        new_network_name,
                    )

        logger.debug("Generated rt: %s", final_routing_table)
        return final_routing_table

    def _sync_routing_tables(self) -> None:
        """Syncs the internal routing table with all of the requirer's app databags."""
        routing_table = self.get_routing_table()
        for relation in self.model.relations[self.relation_name]:
            relation.data[self.charm.app].update({"networks": json.dumps(routing_table)})
        logger.info("Resynchronized routing tables with %s", routing_table)


class RouterRequires(Object):
    """This class is used by ip-router requirers to create new network requests.
    This requested network will be uniquely assigned to the requirer that created
    it by the router provider, and it will also be broadcast to all of the other
    ip-router requirer's databags by the ip-router provider.

    At the same time, this class also provides the ability to get all of the other
    networks that were assigned by the ip-router provider. A collective routing
    table is created by the ip-router provider, which can be accessed at any
    time from this class, or from listening to the `routing_table_updated` event.

    This library can be used to share a routing table with assigned IP's between
    multiple requirer charms, but the actual implementation of the pathing between
    IP's is left to the provider and requirer charms themselves.

    Attributes:
        charm:
            The Charm object that instantiates this class.
        relation_name:
            The name used for the relation implementing the ip-router interface.
    """

    on = RouterRequirerCharmEvents()

    def __init__(self, charm: CharmBase, relation_name: str = "ip-router"):
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name
        self.framework.observe(
            charm.on[relation_name].relation_changed, self._router_relation_changed
        )

    def _router_relation_changed(self, event: RelationChangedEvent):
        new_table = self.get_routing_table()
        self.on.routing_table_updated.emit({"networks": new_table})

    def request_network(self, requested_networks: RoutingTable) -> None:
        """Requests a set of new networks from the ip-router provider. Multiple
        calls to this function will replace the previously requested networks,
        so all of the networks required must be given with each call. If successful,
        the provider will reserve this network for the charm and broadcast the
        availability of this network to all other requirers.

        Arguments:
            requested_networks:
                An object of type RoutingTable that the requirer wants from the
                router to assign to itself, as well as broadcast to other requirers.

        Raises:
            ValueError:
                Validation of one or more of the networks failed.
            KeyError:
                Validation of one or more of the networks failed.
        """
        if not self.charm.unit.is_leader():
            return

        ip_router_relations = self.model.relations.get(self.relation_name)
        if len(ip_router_relations) == 0:
            return

        existing_routing_table = self.get_routing_table()
        [existing_routing_table.pop(key, None) for key in requested_networks.keys()]

        for network_name, network_request in requested_networks.items():
            try:
                _validate_network(network_request, existing_routing_table)
            except (ValueError, KeyError) as e:
                logger.error(
                    "Exception (%s) occurred with network request. No routes were added.",
                    e.args[0],
                )
                raise
            else:
                existing_routing_table[network_name] = network_request

        for relation in ip_router_relations:
            relation.data[self.charm.app].update({"networks": json.dumps(requested_networks)})
        logger.debug(
            "Requested new network from the routers %s",
            str([r.name for r in ip_router_relations]),
        )

    def get_routing_table(self) -> RoutingTable:
        """Fetches combined routing tables made available by ip-router providers

        Returns:
            An object of type `RoutingTable` as defined in this file.
        """
        if not self.charm.unit.is_leader():
            return

        router_relations = self.model.relations.get(self.relation_name)
        validated_routing_table: RoutingTable = {}
        for relation in router_relations:
            if relation_data := relation.data[relation.app].get("networks"):
                try:
                    routing_table_from_databag: RoutingTable = json.loads(relation_data)
                except json.decoder.JSONDecodeError:
                    logger.error(
                        "The router's databag has been misconfigured. Can't build routing table."
                    )
                    return {}

                for network_name, network_entry in routing_table_from_databag.items():
                    try:
                        _validate_network(network_entry, validated_routing_table)
                    except (ValueError, KeyError) as e:
                        logger.warning(
                            "Malformed network detected in the databag:\nNetwork: (%s)\nError: (%s)",
                            network_entry,
                            e.args[0],
                        )
                    else:
                        validated_routing_table[network_name] = network_entry
                logger.debug(
                    "Read networks from app: (%s) and relation: (%s)",
                    relation.app.name,
                    self.relation_name,
                )
        return validated_routing_table

    def get_network(self, network_name: str) -> Network:
        """Fetches the network configuration of a specific network.

        Args:
            network_name:
                The requested network name
        Returns:
            An object of type Network
        Raises:
            KeyError: 
               Will raise if the network_name does not yet exist in the routing table"""
        return self.get_routing_table()[network_name]
