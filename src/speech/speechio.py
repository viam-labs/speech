from typing import ClassVar, Mapping, Sequence
from enum import Enum
import time
import os
import json
import hashlib
from typing_extensions import Self

from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import Model
from viam import logging

from pygame import mixer
import elevenlabs as eleven
import pygame._sdl2 as sdl2
from gtts import gTTS
import openai
import speech_recognition as sr

from .api import SpeechService
LOGGER = logging.getLogger(__name__)

mixer.init(buffer=1024)

class SpeechProvider(Enum):
    google = "google"
    elevenlabs = "elevenlabs"

class CompletionProvider(Enum):
    openaigpt35turbo = "openaigpt35turbo"

class SpeechIOService(SpeechService, Reconfigurable):
    """This is the specific implementation of a ``SpeechService`` (defined in api.py)

    It inherits from SpeechService, as well as conforms to the ``Reconfigurable`` protocol, which signifies that this component can be
    reconfigured. It also specifies a function ``SpeechIOService.new``, which conforms to the ``resource.types.ResourceCreator`` type,
    which is required for all models.
    """

    MODEL: ClassVar[Model] = Model.from_string("viamlabs:speech:speechio")
    speech_provider: SpeechProvider
    speech_provider_key: str
    speech_voice: str
    completion_provider: CompletionProvider
    completion_provider_org: str
    completion_provider_key: str
    listen: bool
    listen_trigger_say: str
    listen_trigger_completion: str
    listen_trigger_command: str
    listen_command_buffer_length: int

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        speechio = cls(config.name)
        speechio = speechio.reconfigure(config, dependencies)

        LOGGER.debug(json.dumps(speechio.__dict__))
        return speechio

    async def say(self, text: str) -> str:
        if str == "":
            raise ValueError("No text provided")

        file = 'cache/' + self.speech_provider + self.speech_voice + hashlib.md5(text.encode()).hexdigest() + ".mp3"
        try:
            if not os.path.isfile(file): # read from cache if it exists
                if (self.speech_provider == 'elevenlabs'):
                        audio = eleven.generate(text=text, voice=self.speech_voice)
                        time.sleep(1)
                        eleven.save(audio=audio, filename=file)
                        time.sleep(1)
                else:
                    sp = gTTS(text=text, lang='en', slow=False)
                    sp.save(file)
            mixer.music.load(file) 
            mixer.music.play() # Play it

            while mixer.music.get_busy():
                time.sleep(1)
        except RuntimeError:
            raise ValueError("Say speech failure")

        return text

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        self.speech_provider = config.attributes.fields["speech_provider"].string_value or 'google'
        self.speech_provider_key = config.attributes.fields["speech_provider_key"].string_value or ''
        self.speech_voice = config.attributes.fields["speech_voice"].string_value or 'Josh'
        self.completion_provider = config.attributes.fields["completion_provider"].string_value or 'openaigpt35turbo'
        self.completion_provider_org = config.attributes.fields["completion_provider_org"].string_value or ''
        self.completion_provider_key = config.attributes.fields["completion_provider_key"].string_value or ''
        self.listen = config.attributes.fields["listen"].bool_value or False
        self.listen_trigger_say = config.attributes.fields["listen_trigger_say"].string_value or "robot say"
        self.listen_trigger_completion = config.attributes.fields["listen_trigger_completion"].string_value or "hey Robot"
        self.listen_trigger_command = config.attributes.fields["listen_trigger_command"].string_value or "robot now"
        self.listen_command_buffer_length = config.attributes.fields["listen_command_buffer_length"].number_value or 10

        if self.speech_provider == 'elevenlabs' and self.speech_provider_key != '':
            eleven.set_api_key(self.speech_provider_key)
        else:
            self.speech_provider = 'google'
        
        return self