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
from ops import RelationJoinedEvent, StoredState
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
    Charm event for when the network topology changes, all hosts are notified that there are new routes in the databag
    """


class NewNetworkRequestEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """

    def __init__(self, handle, routing_table: RoutingTable = None):
        super().__init__(handle)
        self.rt = routing_table

    def snapshot(self):
        return {"data": self.rt}

    def restore(self, snapshot):
        self.rt = snapshot["data"]


class RouterProviderCharmEvents(ObjectEvents):
    """List of events"""

    new_network_request = EventSource(NewNetworkRequestEvent)


class RouterRequirerCharmEvents(ObjectEvents):
    """Some docstring"""

    routing_table_updated = EventSource(RoutingTableUpdatedEvent)
    new_network_request = EventSource(NewNetworkRequestEvent)


class RouterProvides(Object):
    """
    This class is used to manage the routing table of the router provider, to be instantiated by the Provider.

    It has functionality to do CRUD operations on the internal table, and it automatically
    keeps the routing table inside all of the charm's relation databags in sync.
    """

    _stored = StoredState()
    on = RouterProviderCharmEvents()

    def __init__(self, charm: CharmBase):
        """Init."""
        super().__init__(charm, "router")
        self.charm = charm
        self._stored.set_default(routing_table={})
        self.framework.observe(self.on.new_network_request, self._on_new_network_request)
        self.framework.observe(
            self.charm.on.ip_router_relation_joined, self._on_ip_router_relation_joined
        )

    def _on_ip_router_relation_joined(self, event: RelationJoinedEvent):
        # Assumes the unit name is unique
        logger.warning(self._stored.routing_table)
        self._stored.routing_table.update({event.unit.name: {}})
        logger.warning(self._stored.routing_table)

    def _on_new_network_request(self, event: NewNetworkRequestEvent):
        if not self.model.unit.is_leader():
            return

        # TODO: Check that the network isn't taken by any other unit

        # TODO: Merge new request with the existing routing table
        logger.warning(event)
        logger.warning(event.unit.name)
        logger.warning(event.app.name)
        unit_name = event.unit
        existing_table = self._stored.routing_table
        new_request = event.rt

        logger.debug(f"Updating\n{existing_table} \nWith:\n {new_request}\n From: {app_name}")

        existing_table[unit_name].update(new_request)

        # TODO: Sync this table with each relation's application databag
        self._sync_routing_tables()
        self.charm.on.routing_table_updated.emit()

    def get_routing_table(self):
        """
        Read only way to get the current routing table
        """
        return deepcopy(self._stored.routing_table._under)

    def _sync_routing_tables(self):
        """
        Syncs the internal routing table with all of the relation's app databags
        """
        # TODO: Implement
        for relation, relation_data in self.model.relations.items():
            logger.warning(f"{relation} --- {relation_data}")


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
        # TODO: Validate

        self.charm.on.new_network_request.emit(network)

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
        current_rt = self.get_routing_table()
        pass

    def get_routing_table(self):
        """
        Finds the relation databag with the provider of ip-router and returns the network table found within
        """
        my_relations = self.model.relations
        router_relations = my_relations["ip-router"]

        # TODO: find the correct bag
        for relation in router_relations:
            logger.debug(relation)

        # TODO: take and return rt
