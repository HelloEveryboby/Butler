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
        with grpc.insecure_channel(target) as channel:
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

    def list_nodes(self):
        return self.nodes

    def stop(self):
        if self.zc:
            self.zc.close()

cluster_manager = ClusterManager()
