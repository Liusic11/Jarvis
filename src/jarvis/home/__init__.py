"""家庭语义层：房间 / 设备的逻辑视图与 entity_id 映射。"""

from .topology import (
    DEFAULT_TOPOLOGY_PATH,
    VALID_CAPABILITIES,
    Device,
    Resolution,
    Room,
    Topology,
    TopologyError,
    TopologyErrorCode,
    load_topology,
    parse_topology,
)

__all__ = [
    "DEFAULT_TOPOLOGY_PATH",
    "VALID_CAPABILITIES",
    "Device",
    "Resolution",
    "Room",
    "Topology",
    "TopologyError",
    "TopologyErrorCode",
    "load_topology",
    "parse_topology",
]
