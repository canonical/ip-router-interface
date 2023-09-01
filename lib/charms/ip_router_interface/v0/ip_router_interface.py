"""TODO: Add a proper docstring here.

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
from typing import Dict, List, Union
from ops.framework import EventBase

RoutingTable = Dict[
    Dict[
        List[
            Dict[
                str,
                Union[
                    IPv4Network,
                    IPv4Address,
                    Dict[List[Dict[str, Union[IPv4Network, IPv4Address]]]],
                ],
            ]
        ]
    ]
]


class Router:
    """
    This class is used to manage the routing table of the router provider.

    It has functionality to do CRUD operations on the internal table, and it automatically
    keeps the routing table inside all of the charm's relation databags in sync.
    """

    routing_table: RoutingTable = {}

    @classmethod
    def get_routing_table(cls) -> RoutingTable:
        """
        returns the current state of the internal routing table
        """
        return cls.routing_table

    @classmethod
    def set_routing_table(cls, table: RoutingTable):
        """
        set a custom routing table
        """
        cls.routing_table = table

    @classmethod
    def add_interface(cls, app_name: str, interface: IPv4Interface):
        """
        Add a new interface to the internal routing table
        """
        cls.routing_table[app_name]["networks"].append(
            {"gateway": interface.ip, "network": interface.network}
        )

    @classmethod
    def add_route(cls, interface: IPv4Interface, new_route: IPv4Interface):
        """
        Adds a new route to an interface in the routing table
        """
        pass

    @classmethod
    def remove_route(cls, interface: IPv4Interface):
        """
        Removes an existing route from the routing table
        """
        pass

    @classmethod
    def _sync_routing_table(cls):
        """
        Syncs the internal routing table with all of the relation's app databags
        """
        pass


class Host:
    """
    This class is used to interact with the routing information within the databag.
    Unlike the router, this class holds no internal state, and is only used to keep
    router requirer functionality in a logical group.
    """

    @staticmethod
    def get_routing_table() -> RoutingTable:
        """
        Get the most recent routing table from the router in its entirety.
        """

    @staticmethod
    def get_interfaces():
        """
        Get the names of all of the available interfaces
        """

    @staticmethod
    def get_interface(app_name: str):
        """
        Get the interface information of a specific app in the router, and raise an error if not found
        """

    @staticmethod
    def request_route(interface: IPv4Interface):
        """
        Request a specific route from the router
        """
        pass


class RoutingTableUpdatedEvent(EventBase):
    """
    Charm event for when the network topology changes, all hosts are notified that there are new routes in the databag
    """


class NewInterfaceRequestEvent(EventBase):
    """
    Charm event for when a host registers a new interface to the router.
    """


class NewRouteRequestEvent(EventBase):
    """
    Charm event for when a host registers a route to an existing interface in the router
    """
