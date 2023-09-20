"""
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
from ops import RelationJoinedEvent, RelationChangedEvent, StoredState
import logging

logger = logging.getLogger(__name__)


RoutingTable = Dict[
    str,  # Name of the application
    Dict[  # All networks for this application
        str,  # always 'networks'
        List[  # list of networks
            Dict[
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
        ],
    ],
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

    def _on_ip_router_relation_joined(self, event: RelationJoinedEvent):
        """
        When a new unit or app joins the relation, we add its name to the
        routing table. This allows the user to differentiate between units
        that don't exist and units that haven't requested a new network yet.
        """
        self._stored.routing_table.update({event.app.name: {"networks": []}})

    def _on_ip_router_relation_changed(self, event: RelationChangedEvent):
        """
        This function updates the internal routing table state to reflect changes in
        requirer units' new network requests.
        """
        if not self.charm.unit.is_leader():
            return

        new_network = event.relation.data[event.relation.app.name]["networks"]

        # Validate
        # if gateway not in existing_network.network:
        #     logger.error("The path to the new route is not from the given network")

        # Update the routing table
        self._stored.routing_table[event.relation.app.name]["networks"].append(new_network)

        # Sync and update
        self._sync_routing_tables()
        self.on.routing_table_updated.emit()

    def get_routing_table(self):
        """
        Read-only way to get the current routing table
        """
        return deepcopy(self._stored.routing_table._under)

    def _sync_routing_tables(self):
        """
        Syncs the internal routing table with all of the relation's app databags
        """
        ip_router_relations = self.model.relations["ip-router"]
        for relation in ip_router_relations:
            relation.data[self.charm.app.name] = self.get_routing_table()


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

    def request_network(self, network: IPv4Interface):
        """
        Arguments: IPv4 interface, like '192.168.1.25/24'. It must not be assigned previously.
        """
        # TODO: Validate if there is no other network with this

        if not self.unit.is_leader():
            return

        # Format the input
        new_network = {"networks": [{"gateway": network.ip, "network": network.network}]}

        # Place it in the databags
        for relation in self.model.relations.get("ip-router"):
            relation.data[self.charm.app.name] = new_network

        self.on.new_network_request.emit()

    def request_route(
        self, existing_network: IPv4Network, destination: IPv4Network, gateway: IPv4Address
    ):
        """Requests a new route from the router provider.
        The gateway to the route must be within an existing network
        assigned to the requesting unit.

        Arguments:
            existing_network: an IPv4 Network that's created by the requesting unit
            destination: an IPv4 Network that is the route within the gateway
            gateway: an IPv4 Address that's within the existing network that will be used to route to the destination.
        """
        # TODO: validate that gateway is within the existing network
        # TODO: we can just find it in the RT automatically in the future
        self.on.new_route_request.emit(
            {"existing_network": existing_network, "destination": destination, "gateway": gateway}
        )

    def get_routing_table(self):
        """
        Finds the relation databag with the provider of ip-router and returns the network table found within
        """
        router_relations = self.model.relations.get("ip-router")

        all_routers = []
        for relation in router_relations:
            all_routers.append(relation.data[relation.app.name])

        return all_routers
