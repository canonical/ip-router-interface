""" TODO: This whole thing, type hints, docstrings
Example Usage:
# ...
from charms.ip_router_inteface.v0.ip_router_interface import RouterProvides
#...

class SpecialCharm(CharmBase):
    # ...
    on = RouterProviderCharmEvents()
    # ...
    def __init__(self, *args):
        super().__init__(*args)
        # ...
        self.demo = RouterProvides(self, self._stored)
        self.framework.observe(self.on.new_network_request, self._on_new_network_request)
        # ...

This is a placeholder docstring for this charm library. Docstrings are
presented on Charmhub and updated whenever you push a new version of the
library.

Complete documentation about creating and documenting libraries can be found
in the SDK docs at https://juju.is/docs/sdk/libraries.

See `charmcraft publish-lib` and `charmcraft fetch-lib` for details of how to
share and consume charm libraries. They serve to enhance collaboration
between charmers. Use a charmer's libraries for classes that handle
integration with their charm.

Bear in mind that new revisions of the different major API versions (v0, v1,
v2 etc) are maintained independently.  You can continue to update v0 and v1
after you have pushed v3.

Markdown is supported, following the CommonMark specification.
"""

# The unique Charmhub library identifier, never change it
LIBID = "8bed752769244d9ba01c61d5647683cf"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

from ipaddress import IPv4Interface, IPv4Address, IPv4Network
from copy import deepcopy
from typing import Dict, List, Union
from ops.framework import EventBase, Object, EventSource, ObjectEvents
from ops.charm import CharmBase, CharmEvents
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
    Dict[str, List[Network]],  # All networks for this application  # always 'networks'
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
    """
    This class is used to manage the routing table of the router provider,
    to be instantiated by the Provider.

    It's used to:
    * Manage the routing table in the charm itself, by adding and removing
    new network and route requests by integrated units,
    * Syncronize the databags of all requiring units with the router table of the
    provider charm

    """

    _stored = StoredState()
    on = RouterProviderCharmEvents()

    def __init__(self, charm: CharmBase):
        """Init."""
        super().__init__(charm, "router")
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
        """
        When a new unit or app joins the relation, we add its name to the
        routing table.
        """
        self._stored.routing_table.update({event.relation.app.name: {"networks": []}})
        self._sync_routing_tables()

    def _on_ip_router_relation_changed(self, event: RelationChangedEvent):
        """
        This function updates the internal routing table state to reflect changes in
        requirer units' new network requests.
        """
        if not self.charm.unit.is_leader():
            return

        new_network = event.relation.data[event.relation.app]["networks"]

        # Update the routing table
        self._stored.routing_table[event.relation.app.name] = new_network

        # Sync and update
        self._sync_routing_tables()

    def _on_ip_router_relation_departed(self, event: RelationDepartedEvent):
        """
        If an application has completely departed the relation, remove it
        from the routing table.
        """
        if len(event.relation.units) == 0:
            self._stored.routing_table.pop(event.app.name)
            self._sync_routing_tables()

    def get_routing_table(self):
        """
        Read-only way to get the current routing table
        """
        return deepcopy(self._stored.routing_table._under)

    def get_flattened_routing_table(self):
        """
        Read-only routing table that's flattened to fit the specification
        """
        internal_rt = self.get_routing_table()
        final_rt = []
        for networks in internal_rt.values():
            if type(networks) is not str:
                continue
            for network in json.loads(networks):
                final_rt.append(network)

        return final_rt

    def _sync_routing_tables(self):
        """
        Syncs the internal routing table with all of the relation's app databags
        """
        ip_router_relations = self.model.relations["ip-router"]
        for relation in ip_router_relations:
            relation.data[self.charm.app].update(
                {"networks": json.dumps(self.get_flattened_routing_table())}
            )


class RouterRequires(Object):
    """
    This class is used to interact with the routing information within the databag.
    Unlike the router, this class holds no internal state, and is only used to keep
    router requirer functionality in a logical group.
    """

    on = RouterRequirerCharmEvents()

    def __init__(self, charm: CharmBase):
        super().__init__(charm, "ip-router")
        self.charm = charm

    def request_network(
        self,
        networks: List[Network],
    ):
        """
        Arguments:
            TODO: write the docstring
        """
        if not self.charm.unit.is_leader():
            return

        valid_requests = []
        for network_request in networks:
            if self._network_is_valid(network_request):
                valid_requests.append(network_request)

        # Place it in the databag
        for relation in self.model.relations.get("ip-router"):
            relation.data[self.charm.app].update({"networks": json.dumps(valid_requests)})

    def get_all_networks(self):
        """
        Finds the relation databag with the provider of ip-router and returns the network table found within
        """
        if not self.charm.unit.is_leader():
            return

        router_relations = self.model.relations.get("ip-router")

        all_networks = []
        for relation in router_relations:
            if networks := relation.data[relation.app].get("networks"):
                all_networks.extend(json.loads(networks))
        return all_networks

    def _network_is_valid(self, network_request: Network):
        """This function validates the"""
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
