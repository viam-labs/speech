"""
This file registers the speech subtype with the Viam Registry, as well as the specific SpeechIOService model.
"""

from viam.resource.registry import Registry, ResourceCreatorRegistration

from speech_service_api import SpeechService
from .speechio import SpeechIOService

Registry.register_resource_creator(SpeechService.SUBTYPE, SpeechIOService.MODEL, ResourceCreatorRegistration(SpeechIOService.new))
