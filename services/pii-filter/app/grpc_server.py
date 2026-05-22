import asyncio

import grpc

from app import pii_pb2, pii_pb2_grpc
from app.redactor import redact

GRPC_PORT = 50051


class PiiFilterServicer(pii_pb2_grpc.PiiFilterServicer):
    async def Redact(self, request, context):
        text, decision, warning = redact(
            text=request.text,
            source=request.source,
            given_name=request.given_name,
        )
        return pii_pb2.RedactResponse(
            text=text,
            decision=decision,
            warning_message=warning,
        )


async def serve() -> None:
    server = grpc.aio.server()
    pii_pb2_grpc.add_PiiFilterServicer_to_server(PiiFilterServicer(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
