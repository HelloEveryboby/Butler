import grpc
import json
import logging
from typing import Dict, Any, List
from docs import butler_agent_pb2
from docs import butler_agent_pb2_grpc
from butler.core.discovery import browse_butler_services

logger = logging.getLogger("ClusterManager")

class ClusterManager:
    """
    Butler 集群管理中心 (Master 端)。
    管理局域网内的所有 Agent 节点，并进行任务分发。
    """
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.zc = None
        self.browser = None

    def start_discovery(self):
        self.zc, self.browser = browse_butler_services(self._on_node_found)
        logger.info("Cluster discovery started.")

    def _on_node_found(self, name: str, address: str, port: int, properties: dict):
        node_id = name.split('.')[0]
        if node_id not in self.nodes:
            logger.info(f"New Agent detected: {node_id} at {address}:{port}")
            self.nodes[node_id] = {
                "address": address,
                "port": port,
                "properties": properties,
                "status": "online"
            }

    def execute_remote(self, node_id: str, skill_id: str, action: str, payload: dict):
        node = self.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found.")

        target = f"{node['address']}:{node['port']}"
        # Use mTLS if certificates are available
        creds = self._get_credentials()
        channel_factory = grpc.secure_channel if creds else grpc.insecure_channel

        with channel_factory(target, creds) as channel:
            stub = butler_agent_pb2_grpc.ButlerAgentStub(channel)
            request = butler_agent_pb2.TaskRequest(
                skill_id=skill_id,
                action=action,
                payload_json=json.dumps(payload, ensure_ascii=False)
            )
            response = stub.ExecuteTask(request)
            if response.success:
                return json.loads(response.result_json)
            else:
                raise RuntimeError(f"Remote execution failed: {response.error}")

    def _get_credentials(self):
        """Load or generate self-signed mTLS credentials."""
        # Simplified placeholder for certificate loading
        return None

    def list_nodes(self):
        return self.nodes

    def air_drop_push(self, node_id: str, payload: Dict[str, Any]):
        """
        Pushes a MsgPack/JSON payload via gRPC P2P pipeline.
        Triggered by 'Swipe Up' gesture.
        """
        return self.execute_remote(node_id, "cluster_manager", "airdrop_in", payload)

    def stop(self):
        if self.zc:
            self.zc.close()

cluster_manager = ClusterManager()
