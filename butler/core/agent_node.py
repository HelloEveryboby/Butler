import grpc
import json
import logging
import socket
from concurrent import futures
from docs import butler_agent_pb2
from docs import butler_agent_pb2_grpc
from butler.core.skill_manager import SkillManager
from butler.core.algorithms import dras_manager
from butler.core.discovery import ButlerServiceDiscovery

logger = logging.getLogger("ButlerAgent")

class ButlerAgentServicer(butler_agent_pb2_grpc.ButlerAgentServicer):
    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager

    def ExecuteTask(self, request, context):
        logger.info(f"Received remote task: {request.skill_id}:{request.action}")
        try:
            payload = json.loads(request.payload_json)
            result = self.skill_manager.execute(request.skill_id, request.action, **payload)
            return butler_agent_pb2.TaskResponse(
                success=True,
                result_json=json.dumps(result, ensure_ascii=False)
            )
        except Exception as e:
            return butler_agent_pb2.TaskResponse(
                success=False,
                error=str(e)
            )

    def GetSystemStatus(self, request, context):
        stats = dras_manager.get_system_stats()
        return butler_agent_pb2.StatusResponse(
            cpu_usage=stats["cpu"],
            memory_usage=stats["memory"],
            hostname=socket.gethostname()
        )

def serve_agent(port=50051):
    skill_manager = SkillManager()
    skill_manager.load_skills()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    butler_agent_pb2_grpc.add_ButlerAgentServicer_to_server(
        ButlerAgentServicer(skill_manager), server
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()

    # 注册 mDNS 服务
    discovery = ButlerServiceDiscovery()
    discovery.register_service(f"ButlerAgent-{socket.gethostname()}", port, {"role": "agent"})

    logger.info(f"Butler Agent serving on port {port}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        discovery.close()
        server.stop(0)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve_agent()
