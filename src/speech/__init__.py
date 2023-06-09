"""
This file registers the speech subtype with the Viam Registry, as well as the specific SpeechIOService model.
"""

from viam.resource.registry import Registry, ResourceCreatorRegistration, ResourceRegistration

from .api import SpeechClient, SpeechRPCService, SpeechService
from .speechio import SpeechIOService

Registry.register_subtype(ResourceRegistration(SpeechService, SpeechRPCService, lambda name, channel: SpeechClient(name, channel)))

Registry.register_resource_creator(SpeechService.SUBTYPE, SpeechIOService.MODEL, ResourceCreatorRegistration(SpeechIOService.new))