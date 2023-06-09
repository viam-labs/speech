"""
This file outlines the general structure for the API around a custom, modularized service.

It defines the abstract class definition that all concrete implementations must follow,
the gRPC service that will handle calls to the service,
and the gRPC client that will be able to make calls to this service.

In this example, the ``Speech`` abstract class defines what functionality is required for all Speech services.
It extends ``ServiceBase``, as all service types must.
It also defines its specific ``SUBTYPE``, which is used internally to keep track of supported types.

The ``SpeechRPCService`` implements the gRPC service for the Speech service. This will allow other robots and clients to make
requests of the Speech service. It extends both from ``SpeechServiceBase`` and ``RPCServiceBase``.
The former is the gRPC service as defined by the proto, and the latter is the class that all gRPC services must inherit from.

Finally, the ``SpeechClient`` is the gRPC client for a Speech service. It inherits from SpeechService since it implements
 all the same functions. The implementations are simply gRPC calls to some remote Speech service.

To see how this custom modular service is registered, see the __init__.py file.
To see the custom implementation of this service, see the speechio.py file.
"""

import abc
from typing import Final, Sequence

from grpclib.client import Channel
from grpclib.server import Stream

from viam.resource.rpc_service_base import ResourceRPCServiceBase
from viam.resource.types import RESOURCE_TYPE_SERVICE, Subtype
from viam.services.service_base import ServiceBase

from ..proto.speech_grpc import SpeechServiceBase, SpeechServiceStub
from ..proto.speech_pb2 import SayRequest, SayResponse


class SpeechService(ServiceBase):
    """Example service to use with the example module"""

    SUBTYPE: Final = Subtype("viamlabs", RESOURCE_TYPE_SERVICE, "speech")

    @abc.abstractmethod
    async def say(self, text: str) -> str:
        ...


class SpeechRPCService(SpeechServiceBase, ResourceRPCServiceBase):
    """Example gRPC service for the Speech service"""

    RESOURCE_TYPE = SpeechService

    async def Say(self, stream: Stream[SayRequest, SayResponse]) -> None:
        request = await stream.recv_message()
        assert request is not None
        name = request.name
        service = self.get_resource(name)
        resp = await service.say(request.text)
        await stream.send_message(SayResponse(said=resp))


class SpeechClient(SpeechService):
    """Example gRPC client for the Speech Service"""

    def __init__(self, name: str, channel: Channel) -> None:
        self.channel = channel
        self.client = SpeechServiceStub(channel)
        super().__init__(name)

    async def say(self, text: str) -> str:
        request = SayRequest(name=self.name, text=text)
        response: SayResponse = await self.client.Say(request)
        return response.text