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
    Charm event for when the network routing table changes.
    """


class NewNetworkRequestEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """

    def __init__(self, handle, network=None):
        super().__init__(handle)
        self.network = network

    def snapshot(self):
        return {"data": self.network}

    def restore(self, snapshot):
        self.network = snapshot["data"]


class NewRouteRequestEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """

    def __init__(self, handle, routing_table: RoutingTable = None):  # TODO
        super().__init__(handle)
        self.rt = routing_table

    def snapshot(self):
        return {"data": self.rt}

    def restore(self, snapshot):
        self.rt = snapshot["data"]


class RouterProviderCharmEvents(ObjectEvents):
    new_network_request = EventSource(NewNetworkRequestEvent)
    routing_table_updated = EventSource(RoutingTableUpdatedEvent)


class RouterRequirerCharmEvents(ObjectEvents):
    routing_table_updated = EventSource(RoutingTableUpdatedEvent)
    new_network_request = EventSource(NewNetworkRequestEvent)


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
        self.framework.observe(self.on.new_network_request, self._on_new_network_request)
        self.framework.observe(
            self.charm.on.ip_router_relation_joined, self._on_ip_router_relation_joined
        )

    def _on_ip_router_relation_joined(self, event: RelationJoinedEvent):
        """
        When a new unit or app joins the relation, we add its name to the
        routing table. This allows the user to differentiate between units
        that don't exist and units that haven't requested a new network yet.
        """
        self._stored.routing_table.update({event.unit.name: {"networks": []}})

    def _on_new_network_request(self, event: NewNetworkRequestEvent):
        """This function attempts to add a new network to the routing table.
        TODO: Figure out a sensible response to failiures due to the race condition.

        Args:
            network: The requested network, in the format of <gateway>/<mask>
            eg. 192.168.250.1/24. The IP will be used as the gateway, and the
            mask will be used as the network.

        Returns:
            Nothing
        """
        unit_name = event.unit.name
        requested_network: IPv4Interface = IPv4Interface(event.params["network"])

        if not self.model.unit.is_leader():
            return
        # for networks in self._stored.routing_table.values():
        #     for network_list in networks.values():
        #         network = IPv4Network(network_list["network"])
        #         if requested_network.ip in network:
        #             logger.error("This network is already taken")
        #             # TODO: This could happen if requests are made in parallel. What to do here?
        #             return

        # Merge new request with the existing routing table
        logger.debug(
            f"\nUpdating\n{self._stored.routing_table}\nWith:\n{event.params}\nFrom: {unit_name}"
        )
        new_network = {
            "network": str(requested_network.network),
            "gateway": str(requested_network.ip),
        }
        self._stored.routing_table[unit_name]["networks"].append(new_network)

        self._sync_routing_tables()
        self.on.routing_table_updated.emit()

    def _on_new_route_request(self, event: NewRouteRequestEvent):
        """This function attempts to add a new route to an existing network.

        Args:
            existing_network: The requested network, in the format of <ip>/<mask>
            eg. 192.168.250.0/24. It is enough for the IP to be within the correct
            network.

            destination: An IP network that will be the destination of the route.

            gateway: The gateway IP for which the user will access the destination route.
            The gateway IP must be within the existing network.

        Returns:
            Nothing
        """
        unit_name = event.unit.name
        existing_network: IPv4Interface = IPv4Interface(event.params["existing_network"])
        destination: IPv4Network = IPv4Network(event.params["destination"])
        gateway: IPv4Address = IPv4Address(event.params["gateway"])

        # Validate
        if gateway not in existing_network:
            logger.error("The path to the new route is not from the given network")

        # Find the relevant network
        for entry in self._stored.routing_table[unit_name]["networks"]:
            network = IPv4Network(entry["network"])
            if existing_network.ip in network:
                found_entry = entry
                break
        else:
            logger.error("There is no network assigned to unit with the given IP")
            return

        # Add the route to the network
        if "routes" not in found_entry.keys():
            found_entry["routes"] = []
        found_entry["routes"].append({"destination": str(destination), "gateway": str(gateway)})

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
        # TODO: Implement
        ip_router_relations = self.model.relations["ip-router"]
        logger.warning(ip_router_relations)


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
