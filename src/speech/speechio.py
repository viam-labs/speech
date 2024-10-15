from io import BytesIO
from typing import ClassVar, Mapping, Optional, Protocol, cast
from enum import Enum
import os
import re
import json
import asyncio
import hashlib
from typing_extensions import Self

from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import Model
from viam.logging import getLogger
from viam.utils import struct_to_dict

import pygame
from pygame import mixer
from elevenlabs.client import ElevenLabs
from elevenlabs import save as eleven_save
from gtts import gTTS
from openai import AsyncOpenAI
import speech_recognition as sr
from pydub import AudioSegment

from speech_service_api import SpeechService


class SpeechProvider(str, Enum):
    google = "google"
    elevenlabs = "elevenlabs"


class CompletionProvider(str, Enum):
    openai = "openai"


class Closer(Protocol):
    def __call__(self, wait_for_stop: bool = True) -> None: ...


class RecState:
    listen_closer: Optional[Closer] = None
    mic: Optional[sr.Microphone] = None
    rec: Optional[sr.Recognizer] = None


LOGGER = getLogger(__name__)
CACHEDIR = "/tmp/cache"

rec_state = RecState()

class SpeechIOService(SpeechService, Reconfigurable):
    """This is the specific implementation of a ``SpeechService`` (defined in api.py)

    It inherits from SpeechService, as well as conforms to the ``Reconfigurable`` protocol, which signifies that this component can be
    reconfigured. It also specifies a function ``SpeechIOService.new``, which conforms to the ``resource.types.ResourceCreator`` type,
    which is required for all models.
    """

    MODEL: ClassVar[Model] = Model.from_string("viam-labs:speech:speechio")
    speech_provider: SpeechProvider
    speech_provider_key: str
    speech_voice: str
    completion_provider: CompletionProvider
    completion_model: str
    completion_provider_org: str
    completion_provider_key: str
    completion_persona: str
    should_listen: bool
    listen_provider: str
    listen_trigger_say: str
    listen_trigger_completion: str
    listen_trigger_command: str
    listen_command_buffer_length: int
    mic_device_name: str
    command_list: list
    trigger_active: bool
    active_trigger_type: str
    disable_mic: bool
    disable_audioout: bool
    openai_client: dict = {}
    eleven_client: dict = {}

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        speechio = cls(config.name)
        speechio.reconfigure(config, dependencies)

        LOGGER.debug(json.dumps(speechio.__dict__))
        return speechio

    async def say(self, text: str, blocking: bool, cache_only: bool = False) -> str:
        if str == "":
            raise ValueError("No text provided")

        LOGGER.info("Generating audio...")
        if not os.path.isdir(CACHEDIR):
            os.mkdir(CACHEDIR)

        file = os.path.join(
            CACHEDIR,
            self.speech_provider.value
            + self.speech_voice
            + self.completion_persona
            + hashlib.md5(text.encode()).hexdigest()
            + ".mp3",
        )
        try:
            if not os.path.isfile(file):  # read from cache if it exists
                if self.speech_provider == "elevenlabs":
                    audio = self.eleven_client["client"].generate(text=text, voice=self.speech_voice)
                    LOGGER.error(audio)
                    eleven_save(audio=audio, filename=file)
                else:
                    sp = gTTS(text=text, lang="en", slow=False)
                    sp.save(file)

            if not cache_only:
                mixer.music.load(file)
                LOGGER.info("Playing audio...")
                mixer.music.play()  # Play it

                if blocking:
                    while mixer.music.get_busy():
                        pygame.time.Clock().tick()

                LOGGER.info("Played audio...")
        except RuntimeError:
            raise ValueError("say() speech failure")

        return text

    async def listen_trigger(self, type: str) -> str:
        if type == "":
            raise ValueError("No trigger type provided")
        if type in ["command", "completion", "say"]:
            self.active_trigger_type = type
            self.trigger_active = True
            if self.should_listen:
                # close and re-open listener so any in-progress speech is not captured
                if rec_state.listen_closer is not None:
                    rec_state.listen_closer(True)
            if rec_state.rec is not None and rec_state.mic is not None:
                rec_state.listen_closer = rec_state.rec.listen_in_background(
                    source=rec_state.mic,
                    phrase_time_limit=self.listen_phrase_time_limit,
                    callback=self.listen_callback,
                )
        else:
            raise ValueError("Invalid trigger type provided")

        return "OK"

    async def is_speaking(self) -> bool:
        return mixer.music.get_busy()

    async def completion(
        self, text: str, blocking: bool, cache_only: bool = False
    ) -> str:
        if text == "":
            raise ValueError("No text provided")
        if self.completion_provider_org == "" or self.completion_provider_key == "":
            raise ValueError(
                "completion_provider_org or completion_provider_key missing"
            )

        completion = ""
        file = os.path.join(
            CACHEDIR,
            self.speech_provider.value
            + self.completion_persona
            + hashlib.md5(text.encode()).hexdigest()
            + ".txt",
        )
        if not cache_only and (self.cache_ahead_completions):
            LOGGER.info("Will try to read completion from cache")
            if os.path.isfile(file):
                LOGGER.info("Cache file exists")
                with open(file) as f:
                    completion = f.read()
                LOGGER.info(completion)

            # now cache next one
            asyncio.ensure_future(self.completion(text, blocking, True))

        if completion == "":
            LOGGER.info("Getting completion...")
            if self.completion_persona != "":
                text = "As " + self.completion_persona + " respond to '" + text + "'"
            completion = await self.openai_client["client"].chat.completions.create(
                model=self.completion_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": text}],
            )
            completion = completion.choices[0].message.content
            completion = re.sub("[^0-9a-zA-Z.!?,:'/ ]+", "", completion).lower()
            completion = completion.replace("as an ai language model", "")
            LOGGER.info("Got completion...")

        if cache_only:
            with open(file, "w") as f:
                f.write(completion)
            asyncio.ensure_future(self.say(completion, blocking, True))
        else:
            await self.say(completion, blocking)
        return completion

    async def get_commands(self, number: int) -> list:
        LOGGER.info("will get " + str(number) + " commands from command list")
        to_return = self.command_list[0:number]
        LOGGER.debug("to return from command_list: " + str(to_return))
        del self.command_list[0:number]
        return to_return

    async def listen(self) -> str:
        if self.stt is not None:
            return await self.stt.listen()

        if rec_state.rec is not None and rec_state.mic is not None:
            with rec_state.mic as source:
                audio = rec_state.rec.listen(source)
            return await self.convert_audio_to_text(audio)

        LOGGER.debug("Nothing to listen to")
        return ""

    async def to_text(self, speech: bytes, format: str = "mp3"):
        if self.stt is not None:
            return await self.stt.to_text(speech, format)

        if rec_state.rec is not None:
            # speech_recognition expects WAV so we need to convert mp3
            sound_out = BytesIO(speech)

            if format != "wav":
                sound = AudioSegment.from_mp3(sound_out)
                sound_out = BytesIO()
                sound.export(sound_out, format=format)

            with sr.AudioFile(sound_out) as source:
                audio = rec_state.rec.record(source)
            return await self.convert_audio_to_text(audio)

        return ""

    async def to_speech(self, text):
        if self.speech_provider == "elevenlabs":
            audio = self.eleven_client["client"].generate(text=text, voice=self.speech_voice)
            return audio
        else:
            mp3_fp = BytesIO()
            sp = gTTS(text=text, lang="en", slow=False)
            sp.write_to_fp(mp3_fp)
            return mp3_fp.getvalue()

    def listen_callback(self, recognizer, audio):
        heard = asyncio.run(self.convert_audio_to_text(audio))
        LOGGER.debug("speechio heard " + heard)

        if heard != "":
            if (
                self.should_listen and re.search(".*" + self.listen_trigger_say, heard)
            ) or (self.trigger_active and self.active_trigger_type == "say"):
                self.trigger_active = False
                to_say = re.sub(".*" + self.listen_trigger_say + "\s+", "", heard)
                asyncio.run(self.say(to_say, blocking=False))
            elif (
                self.should_listen
                and re.search(".*" + self.listen_trigger_completion, heard)
            ) or (self.trigger_active and self.active_trigger_type == "completion"):
                self.trigger_active = False
                to_say = re.sub(
                    ".*" + self.listen_trigger_completion + "\s+", "", heard
                )
                asyncio.run(self.completion(to_say, blocking=False))
            elif (
                self.should_listen
                and re.search(".*" + self.listen_trigger_command, heard)
            ) or (self.trigger_active and self.active_trigger_type == "command"):
                self.trigger_active = False
                command = re.sub(".*" + self.listen_trigger_command + "\s+", "", heard)
                self.command_list.insert(0, command)
                LOGGER.debug("added to command_list: '" + command + "'")
                del self.command_list[self.listen_command_buffer_length :]
            if not self.should_listen:
                # stop listening if not in background listening mode
                LOGGER.debug("will close background listener")
                if rec_state.listen_closer is not None:
                    rec_state.listen_closer()

    async def convert_audio_to_text(self, audio: sr.AudioData) -> str:
        LOGGER.debug(audio)

        if self.stt is not None:
            return await self.stt.to_text(audio.get_wav_data(), format="wav")

        heard = ""

        try:
            # for testing purposes, we're just using the default API key
            # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
            # instead of `r.recognize_google(audio)`
            transcript = rec_state.rec.recognize_google(audio, show_all=True)
            if type(transcript) is dict and transcript.get("alternative"):
                heard = transcript["alternative"][0]["transcript"]
        except sr.UnknownValueError:
            LOGGER.warn("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            LOGGER.warn(
                "Could not request results from Google Speech Recognition service; {0}".format(
                    e
                )
            )
        return heard

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        attrs = struct_to_dict(config.attributes)
        self.speech_provider = SpeechProvider[
            str(attrs.get("speech_provider", "google"))
        ]
        self.speech_provider_key = str(attrs.get("speech_provider_key", ""))
        self.speech_voice = str(attrs.get("speech_voice", "Josh"))
        self.completion_provider = CompletionProvider[
            str(attrs.get("completion_provider", "openai"))
        ]
        self.completion_model = str(attrs.get("completion_model", "gpt-4o"))
        self.completion_provider_org = str(attrs.get("completion_provider_org", ""))
        self.completion_provider_key = str(attrs.get("completion_provider_key", ""))
        if self.completion_provider == "openai":
            self.openai_client["client"] = AsyncOpenAI(
                api_key = self.completion_provider_key,
                organization = self.completion_provider_org
            )
        self.completion_persona = str(attrs.get("completion_persona", ""))
        self.listen_provider = str(attrs.get("listen_provider", "google"))
        self.should_listen = bool(attrs.get("listen", False))
        self.listen_phrase_time_limit = attrs.get("listen_phrase_time_limit", None)
        self.mic_device_name = str(attrs.get("mic_device_name", ""))
        self.listen_trigger_say = str(attrs.get("listen_trigger_say", "robot say"))
        self.listen_trigger_completion = str(
            attrs.get("listen_trigger_completion", "hey robot")
        )
        self.listen_trigger_command = str(
            attrs.get("listen_trigger_command", "robot can you")
        )
        self.listen_command_buffer_length = int(
            attrs.get("listen_command_buffer_length", 10)
        )
        self.cache_ahead_completions = bool(attrs.get("cache_ahead_completions", False))
        self.disable_mic = bool(attrs.get("disable_mic", False))
        self.disable_audioout = bool(attrs.get("disable_audioout", False))
        self.command_list = []
        self.trigger_active = False
        self.active_trigger_type = ""
        self.stt = None

        if (
            self.speech_provider == SpeechProvider.elevenlabs
            and self.speech_provider_key != ""
        ):
            self.eleven_client["client"] = ElevenLabs(
                api_key = self.speech_provider_key
            )
        else:
            self.speech_provider = SpeechProvider.google

        if self.listen_provider != "google":
            stt = dependencies[SpeechService.get_resource_name(self.listen_provider)]
            self.stt = cast(SpeechService, stt)

        if not self.disable_audioout:
            if not mixer.get_init():
                mixer.init(buffer=1024)
        else:
            if mixer.get_init():
                mixer.quit()

        rec_state.rec = sr.Recognizer()

        if not self.disable_mic:
            # set up speech recognition
            if rec_state.listen_closer is not None:
                rec_state.listen_closer(True)
            rec_state.rec.dynamic_energy_threshold = True

            mics = sr.Microphone.list_microphone_names()
            LOGGER.info(mics)

            if self.mic_device_name != "":
                rec_state.mic = sr.Microphone(mics.index(self.mic_device_name))
            else:
                rec_state.mic = sr.Microphone()

            with rec_state.mic as source:
                rec_state.rec.adjust_for_ambient_noise(source, 2)

            # set up background listening if desired
            if self.should_listen:
                LOGGER.debug("Will listen in background")
                rec_state.listen_closer = rec_state.rec.listen_in_background(
                    source=rec_state.mic,
                    phrase_time_limit=self.listen_phrase_time_limit,
                    callback=self.listen_callback,
                )
