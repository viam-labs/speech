from io import BytesIO
from typing import (
    ClassVar,
    Iterator,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    cast,
    Dict,
)
from enum import Enum
from datetime import datetime
import os
import re
import asyncio
import hashlib
import threading
import pyaudio
import json
import time
from typing_extensions import Self
import wave

from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model
from viam.utils import struct_to_dict, ValueTypes

import pygame
from pygame import mixer
from elevenlabs.client import ElevenLabs
from elevenlabs import save as eleven_save
from gtts import gTTS
import openai
import speech_recognition as sr
from pydub import AudioSegment
from google.cloud.speech import (
    RecognizeResponse,
)
from hearken import Listener, EnergyVAD, WebRTCVAD, SileroVAD
from hearken.adapters.sr import SpeechRecognitionSource

try:
    import vosk

    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

from speech_service_api import SpeechService

AUDIO_DIR = os.environ.get(
    "VIAM_MODULE_DATA", os.path.join(os.path.expanduser("~"), ".data", "audio")
)


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
    # Vosk VAD components
    vosk_model: Optional[object] = None
    vosk_rec: Optional[object] = None
    vosk_stream: Optional[object] = None
    vosk_thread: Optional[threading.Thread] = None
    vosk_stop_event: Optional[threading.Event] = None
    # Audio playback interrupt flag
    playback_stop_requested: bool = False


CACHEDIR = "/tmp/cache"

rec_state = RecState()


class SpeechIOService(SpeechService, EasyResource):
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
    stt_provider: str
    stt_provider_config: dict = {}
    listen_trigger_say: str
    listen_trigger_completion: str
    listen_trigger_command: str
    listen_trigger_all: bool
    listen_command_buffer_length: int
    mic_device_name: str
    command_list: list
    trigger_active: bool
    active_trigger_type: str
    disable_mic: bool
    disable_audioout: bool
    eleven_client: Mapping[str, ElevenLabs] = {}
    main_loop: Optional[asyncio.AbstractEventLoop] = None
    listen_trigger_fuzzy_matching: bool
    listen_trigger_fuzzy_threshold: int
    fuzzy_matcher: Optional[object] = None

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        return super().new(config, dependencies)

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        """This method allows you to validate the configuration object received from the machine,
        as well as to return any implicit dependencies based on that `config`.

        Args:
            config (ComponentConfig): The configuration for this resource

        Returns:
            Tuple[Sequence[str], Sequence[str]]: A pair of lists of implicit and optional dependencies
        """
        deps = []
        attrs = struct_to_dict(config.attributes)
        stt_provider = str(attrs.get("stt_provider", ""))
        if stt_provider != "" and "google" not in stt_provider:
            deps.append(stt_provider)
        return deps, []

    async def say(self, text: str, blocking: bool, cache_only: bool = False) -> str:
        if str == "":
            raise ValueError("No text provided")

        self.logger.debug("Generating audio...")
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
                    audio = self.eleven_client["client"].text_to_speech.convert(
                        text=text, **self.speech_generation_config
                    )
                    eleven_save(audio=audio, filename=file)
                else:
                    sp = gTTS(text=text, **self.speech_generation_config)
                    sp.save(file)

            if not cache_only:
                mixer.music.load(file)
                rec_state.playback_stop_requested = (
                    False  # Reset stop flag for new playback
                )
                self.logger.debug("Playing audio...")
                mixer.music.play()  # Play it

                if blocking:
                    while (
                        mixer.music.get_busy() and not rec_state.playback_stop_requested
                    ):
                        pygame.time.Clock().tick(10)

                    # Reset stop flag after breaking out of loop
                    if rec_state.playback_stop_requested:
                        rec_state.playback_stop_requested = False
                        self.logger.debug(
                            "say() blocking loop interrupted by stop request"
                        )

                self.logger.debug("Played audio...")
        except RuntimeError as err:
            self.logger.error(err)
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

    async def stop_playback(self) -> bool:
        """Stop any currently playing audio.

        This method can be called from any thread to interrupt audio playback.
        It will stop the current audio immediately and interrupt any blocking
        wait loops in say().

        Returns:
            bool: True if playback was stopped, False if nothing was playing

        Example:
            # From async context
            await speech_service.stop_playback()

            # From background thread
            asyncio.run_coroutine_threadsafe(
                speech_service.stop_playback(),
                speech_service.main_loop
            )
        """
        if mixer.music.get_busy():
            rec_state.playback_stop_requested = True
            mixer.music.stop()
            self.logger.debug("Playback stopped by external request")
            return True
        return False

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
            self.logger.debug("Will try to read completion from cache")
            if os.path.isfile(file):
                self.logger.debug("Cache file exists")
                with open(file) as f:
                    completion = f.read()
                self.logger.debug(completion)

            # now cache next one
            asyncio.ensure_future(self.completion(text, blocking, True))

        if completion == "":
            self.logger.debug("Getting completion...")
            if self.completion_persona != "":
                text = "As " + self.completion_persona + " respond to '" + text + "'"
            completion = openai.chat.completions.create(
                model=self.completion_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": text}],
            )
            completion = completion.choices[0].message.content
            completion = re.sub("[^0-9a-zA-Z.!?,:'/ ]+", "", completion).lower()
            completion = completion.replace("as an ai language model", "")
            self.logger.debug("Got completion...")

        if cache_only:
            with open(file, "w") as f:
                f.write(completion)
            asyncio.ensure_future(self.say(completion, blocking, True))
        else:
            await self.say(completion, blocking)
        return completion

    async def get_commands(self, number: int) -> list:
        self.logger.debug("will get " + str(number) + " commands from command list")
        to_return = self.command_list[0:number]
        self.logger.debug("to return from command_list: " + str(to_return))
        del self.command_list[0:number]
        return to_return

    async def listen(self) -> str:
        if rec_state.rec is not None and rec_state.mic is not None:
            if self.use_new_listener:
                if segment := self.listener.wait_for_speech():
                    audio = sr.AudioData(
                        segment.audio_data, segment.sample_rate, segment.sample_width
                    )
                else:
                    return ""
            else:
                with rec_state.mic as source:
                    audio = rec_state.rec.listen(source)

            return await self.convert_audio_to_text(audio)

        self.logger.debug("Nothing to listen to")
        return ""

    async def to_text(self, speech: bytes, format: str = "mp3"):
        if self.stt is not None:
            self.logger.debug("using stt provider")
            return await self.stt.to_text(speech, format)

        self.logger.debug(f"using {self.stt_provider} stt")
        if rec_state.rec is not None:
            self.logger.debug("rec_state.rec is not None")

            # Use temporary file for speech_recognition
            import tempfile
            import os

            try:
                # Create temporary file with proper extension
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{format}"
                ) as temp_file:
                    temp_file.write(speech)
                    temp_file_path = temp_file.name

                try:
                    # Convert to WAV if needed
                    if format != "wav":
                        self.logger.debug(f"Converting {format} to WAV")
                        sound = AudioSegment.from_file(temp_file_path, format=format)
                        wav_path = temp_file_path.replace(f".{format}", ".wav")
                        sound.export(wav_path, format="wav")
                        os.unlink(temp_file_path)  # Remove original file
                        temp_file_path = wav_path

                    # Use AudioData.from_file() to create AudioData directly from file
                    audio = sr.AudioData.from_file(temp_file_path)
                    self.logger.debug(
                        f"Created AudioData from file: {len(audio.frame_data)} bytes, {audio.sample_rate}Hz"
                    )

                    return await self.convert_audio_to_text(audio)

                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass

            except Exception as e:
                self.logger.error(f"Error processing audio: {e}")
                return ""

        return ""

    async def to_speech(self, text):
        if self.speech_provider == "elevenlabs":
            audio = self.eleven_client["client"].text_to_speech.convert(
                text=text, **self.speech_generation_config
            )
            if isinstance(audio, Iterator):
                audio = b"".join(audio)
            return audio
        else:
            mp3_fp = BytesIO()
            sp = gTTS(text=text, **self.speech_generation_config)
            sp.write_to_fp(mp3_fp)
            return mp3_fp.getvalue()

    def vosk_vad_callback(self, text: str):
        """Callback for Vosk VAD when speech is detected.

        Note: Vosk doesn't provide alternatives, so fuzzy matching works
        but multi-alternative search is not available.
        """
        self.logger.debug(f"Vosk VAD detected speech: '{text}'")

        if not self.main_loop or not self.main_loop.is_running():
            self.logger.error("Main event loop is not available for Vosk VAD task.")
            return

        # Try fuzzy matching if enabled (no alternatives available with Vosk)
        if text and self.listen_trigger_fuzzy_matching and self.fuzzy_matcher:
            match = self._check_fuzzy_triggers(text, alternatives=None)
            if match:
                self._handle_trigger_match(match)
                return

        # Fall back to existing regex-based matching
        if text != "":
            if (
                self.should_listen
                and re.search(".*" + self.listen_trigger_say, text, re.IGNORECASE)
            ) or (self.trigger_active and self.active_trigger_type == "say"):
                self.trigger_active = False
                to_say = re.sub(
                    ".*" + self.listen_trigger_say + r"\s+",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                asyncio.run_coroutine_threadsafe(
                    self.say(to_say, blocking=False), self.main_loop
                )
            elif (
                self.should_listen
                and re.search(
                    ".*" + self.listen_trigger_completion, text, re.IGNORECASE
                )
            ) or (self.trigger_active and self.active_trigger_type == "completion"):
                self.trigger_active = False
                to_say = re.sub(
                    ".*" + self.listen_trigger_completion + r"\s+",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                asyncio.run_coroutine_threadsafe(
                    self.completion(to_say, blocking=False), self.main_loop
                )
            elif (
                self.should_listen
                and re.search(".*" + self.listen_trigger_command, text, re.IGNORECASE)
            ) or (self.trigger_active and self.active_trigger_type == "command"):
                self.trigger_active = False
                command = re.sub(
                    ".*" + self.listen_trigger_command + r"\s+",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                self.command_list.insert(0, command)
                self.logger.debug("added to command_list: '" + command + "'")
                del self.command_list[self.listen_command_buffer_length :]
            elif self.should_listen and self.listen_trigger_all:
                # Add all speech detections to command queue without prefix requirement
                self.command_list.insert(0, text)
                self.logger.debug("added to command_list (listen_trigger_all): '" + text + "'")
                del self.command_list[self.listen_command_buffer_length :]

    def vosk_vad_thread(self):
        """Vosk VAD thread for voice activity detection"""
        try:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8000,
            )

            rec_state.vosk_stream = stream

            # Track phrase timing for Vosk VAD
            phrase_start_time = None
            phrase_time_limit = self.listen_phrase_time_limit

            while not rec_state.vosk_stop_event.is_set():
                try:
                    data = stream.read(4000, exception_on_overflow=False)

                    # Check if we have speech activity
                    if rec_state.vosk_rec.AcceptWaveform(data):
                        result = json.loads(rec_state.vosk_rec.Result())
                        if result.get("text", "").strip():
                            # Speech detected
                            if phrase_start_time is None:
                                phrase_start_time = time.time()
                                self.logger.debug("Vosk VAD: Phrase started")

                            # Check phrase time limit
                            if phrase_time_limit and phrase_start_time:
                                elapsed_time = time.time() - phrase_start_time
                                if elapsed_time >= phrase_time_limit:
                                    self.logger.debug(
                                        f"Vosk VAD: Phrase time limit reached ({elapsed_time:.1f}s)"
                                    )
                                    # Reset for next phrase
                                    phrase_start_time = None
                                    continue

                            self.vosk_vad_callback(result["text"])
                        else:
                            # No speech detected, reset phrase timing
                            if phrase_start_time is not None:
                                self.logger.debug("Vosk VAD: Phrase ended (no speech)")
                                phrase_start_time = None

                except Exception as e:
                    self.logger.error(f"Vosk VAD error: {e}")
                    break

        except Exception as e:
            self.logger.error(f"Vosk VAD thread error: {e}")
        finally:
            if rec_state.vosk_stream:
                rec_state.vosk_stream.close()
            if p:
                p.terminate()

    def start_vosk_vad(self):
        """Start Vosk VAD if available"""
        if not VOSK_AVAILABLE:
            self.logger.warning(
                "Vosk not available, falling back to speech_recognition VAD"
            )
            return False

        try:
            # Try to load a small Vosk model for VAD
            # You can download models from https://alphacephei.com/vosk/models
            model_path = os.path.expanduser("~/vosk-model-small-en-us-0.15")
            if not os.path.exists(model_path):
                self.logger.debug("Vosk model not found, attempting to download...")
                if self.download_vosk_model():
                    self.logger.debug("Successfully downloaded Vosk model")
                else:
                    self.logger.warning(
                        "Failed to download Vosk model, falling back to speech_recognition VAD"
                    )
                    return False

            rec_state.vosk_model = vosk.Model(model_path)
            rec_state.vosk_rec = vosk.KaldiRecognizer(rec_state.vosk_model, 16000)
            rec_state.vosk_stop_event = threading.Event()

            rec_state.vosk_thread = threading.Thread(
                target=self.vosk_vad_thread, daemon=True
            )
            rec_state.vosk_thread.start()

            self.logger.debug("Started Vosk VAD for voice activity detection")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start Vosk VAD: {e}")
            return False

    def download_vosk_model(self):
        """Download Vosk model automatically"""
        try:
            import urllib.request
            import zipfile

            model_name = "vosk-model-small-en-us-0.15"
            model_url = (
                "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            )
            model_path = os.path.expanduser(f"~/{model_name}")
            zip_path = os.path.expanduser(f"~/{model_name}.zip")

            self.logger.debug(f"Downloading Vosk model from {model_url}")

            # Download the model
            urllib.request.urlretrieve(model_url, zip_path)

            # Extract the model
            self.logger.debug("Extracting Vosk model...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(os.path.expanduser("~/"))

            # Clean up zip file
            os.remove(zip_path)

            # Verify the model was extracted correctly
            if os.path.exists(model_path):
                self.logger.debug(f"Vosk model downloaded successfully to {model_path}")
                return True
            else:
                self.logger.error("Failed to extract Vosk model")
                return False

        except Exception as e:
            self.logger.error(f"Failed to download Vosk model: {e}")
            return False

    def stop_vosk_vad(self):
        """Stop Vosk VAD"""
        if rec_state.vosk_stop_event:
            rec_state.vosk_stop_event.set()
        if rec_state.vosk_thread and rec_state.vosk_thread.is_alive():
            rec_state.vosk_thread.join(timeout=1)
        if rec_state.vosk_stream:
            rec_state.vosk_stream.close()

    def listen_callback(self, recognizer, audio):
        """Process audio with optional fuzzy trigger matching."""
        if not self.main_loop or not self.main_loop.is_running():
            self.logger.error("Main event loop is not available for STT task.")
            return

        self.logger.debug("Listen callback got audio")

        # Get transcript with alternatives if fuzzy matching is enabled
        if self.listen_trigger_fuzzy_matching and self.fuzzy_matcher:
            future = asyncio.run_coroutine_threadsafe(
                self._convert_audio_to_text_with_alternatives(audio), self.main_loop
            )
            try:
                heard, alternatives = future.result(timeout=15)
            except Exception as e:
                self.logger.error(f"STT task failed: {e}")
                return

            # Try fuzzy matching
            if heard:
                self.logger.debug(f"speechio heard: {heard}")
                match = self._check_fuzzy_triggers(heard, alternatives)
                if match:
                    self._handle_trigger_match(match)
                return
        else:
            # Use existing regex-based matching
            future = asyncio.run_coroutine_threadsafe(
                self.convert_audio_to_text(audio), self.main_loop
            )
            try:
                heard = future.result(timeout=15)
            except Exception as e:
                self.logger.error(f"STT task failed: {e}")
                return

        # Existing regex-based trigger detection (fallback or when fuzzy disabled)
        if heard != "":
            self.logger.debug(f"speechio heard: {heard}")

            if (
                self.should_listen
                and re.search(".*" + self.listen_trigger_say, heard, re.IGNORECASE)
            ) or (self.trigger_active and self.active_trigger_type == "say"):
                self.trigger_active = False
                to_say = re.sub(
                    ".*" + self.listen_trigger_say + r"\s+",
                    "",
                    heard,
                    flags=re.IGNORECASE,
                )
                asyncio.run_coroutine_threadsafe(
                    self.say(to_say, blocking=False), self.main_loop
                )
            elif (
                self.should_listen
                and re.search(
                    ".*" + self.listen_trigger_completion, heard, re.IGNORECASE
                )
            ) or (self.trigger_active and self.active_trigger_type == "completion"):
                self.trigger_active = False
                to_say = re.sub(
                    ".*" + self.listen_trigger_completion + r"\s+",
                    "",
                    heard,
                    flags=re.IGNORECASE,
                )
                asyncio.run_coroutine_threadsafe(
                    self.completion(to_say, blocking=False), self.main_loop
                )
            elif (
                self.should_listen
                and re.search(".*" + self.listen_trigger_command, heard, re.IGNORECASE)
            ) or (self.trigger_active and self.active_trigger_type == "command"):
                self.trigger_active = False
                command = re.sub(
                    ".*" + self.listen_trigger_command + r"\s+",
                    "",
                    heard,
                    flags=re.IGNORECASE,
                )
                self.command_list.insert(0, command)
                self.logger.debug("added to command_list: '" + command + "'")
                del self.command_list[self.listen_command_buffer_length :]
            elif self.should_listen and self.listen_trigger_all:
                # Add all speech detections to command queue without prefix requirement
                self.command_list.insert(0, heard)
                self.logger.debug("added to command_list (listen_trigger_all): '" + heard + "'")
                del self.command_list[self.listen_command_buffer_length :]
            if not self.should_listen:
                # stop listening if not in background listening mode
                self.logger.debug("will close background listener")
                if rec_state.listen_closer is not None:
                    rec_state.listen_closer()

    async def convert_audio_to_text(self, audio: sr.AudioData) -> str:
        if self.stt is not None:
            self.logger.debug("getting wav data")
            audio_data = audio.get_wav_data()
            self.logger.debug("using stt provider")
            return await self.stt.to_text(audio_data, format="wav")

        heard = ""

        try:
            self.logger.debug("will convert audio to text")
            response = self._recognize(audio)
            self.logger.debug("transcript: " + str(response))

            if results := self._get_transcripts(response):
                heard = results[0]["transcript"]
                self.logger.debug("heard: " + heard)
        except sr.UnknownValueError:
            self.logger.debug("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            self.logger.error(
                "Could not request results from Google Speech Recognition service; {0}".format(
                    e
                )
            )
        return heard

    async def _convert_audio_to_text_with_alternatives(
        self, audio: sr.AudioData
    ) -> tuple:
        """Convert audio to text with alternatives for fuzzy matching.

        Returns:
            Tuple of (primary_transcript, alternatives_list)
            alternatives_list is None if using external STT provider
        """
        if self.stt is not None:
            # External STT provider - no alternatives available
            text = await self.stt.to_text(audio.get_wav_data(), format="wav")
            return text, None

        try:
            response = self._recognize(audio)
            self.logger.debug("transcript: " + str(response))

            if results := self._get_transcripts(response):
                self.logger.debug(f"Transcript results: {results}")
                primary_text = results[0]["transcript"]
                return primary_text, results

        except sr.UnknownValueError:
            self.logger.debug("Google Speech Recognition could not understand audio")
            if self.save_failed_audio:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                save_audio(audio, f"{AUDIO_DIR}/raw_{timestamp}.wav")
        except sr.RequestError as e:
            self.logger.error(
                f"Could not request results from Google Speech Recognition: {e}"
            )

        return "", None

    def _recognize(self, audio: sr.AudioData):
        if self.stt_provider == "google":
            return rec_state.rec.recognize_google(
                audio, show_all=True, **self.stt_provider_config
            )
        if self.stt_provider == "google_cloud":
            return rec_state.rec.recognize_google_cloud(
                audio, show_all=True, **self.stt_provider_config
            )

    def _get_transcripts(self, response: Dict | RecognizeResponse):
        if isinstance(response, dict):
            return response.get("alternative")
        if isinstance(response, RecognizeResponse) and response.results:
            self.logger.debug(f"RecognizeResponse results: {response.results}")
            return [
                {
                    "transcript": "".join(
                        result.alternatives[0].transcript for result in response.results
                    ),
                    "confidence": response.results[0].alternatives[0].confidence
                    if len(response.results) > 0
                    else 0.0,
                }
            ]

        return None

    def _check_fuzzy_triggers(
        self, heard: str, alternatives: Optional[list]
    ) -> Optional[object]:
        """Check all trigger types using fuzzy matching.

        Args:
            heard: Primary transcript
            alternatives: List of alternative transcriptions

        Returns:
            TriggerMatch if a trigger matched, None otherwise
        """
        triggers = [
            ("say", self.listen_trigger_say),
            ("completion", self.listen_trigger_completion),
            ("command", self.listen_trigger_command),
        ]

        for trigger_type, trigger_phrase in triggers:
            # Check if this trigger should be active
            should_check = self.should_listen or (
                self.trigger_active and self.active_trigger_type == trigger_type
            )

            if not should_check:
                continue

            # Try fuzzy match
            match = self.fuzzy_matcher.match_trigger(
                trigger_phrase, heard, alternatives
            )

            if match:
                self.logger.debug(
                    f"Fuzzy match found: type={trigger_type}, "
                    f"distance={match.distance}, "
                    f"confidence={match.confidence:.2f}, "
                    f"matched='{match.matched_phrase}', "
                    f"alt_index={match.alternative_index}"
                )

                # Add trigger type to match
                match.trigger_type = trigger_type
                return match

        return None

    def _handle_trigger_match(self, match: object):
        """Handle a successful trigger match.

        Args:
            match: TriggerMatch object with match details
        """
        self.trigger_active = False
        command_text = match.command_text

        self.logger.debug(f"Extracted command: '{command_text}'")

        if match.trigger_type == "say":
            asyncio.run_coroutine_threadsafe(
                self.say(command_text, blocking=False), self.main_loop
            )
        elif match.trigger_type == "completion":
            asyncio.run_coroutine_threadsafe(
                self.completion(command_text, blocking=False), self.main_loop
            )
        elif match.trigger_type == "command":
            self.command_list.insert(0, command_text)
            self.logger.debug(f"added to command_list: '{command_text}'")
            del self.command_list[self.listen_command_buffer_length :]

        if not self.should_listen:
            if rec_state.listen_closer is not None:
                rec_state.listen_closer()

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        try:
            self.main_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.main_loop = None
            self.logger.error("Could not get running event loop in reconfigure.")

        attrs = struct_to_dict(config.attributes)
        self.speech_provider = SpeechProvider[
            str(attrs.get("speech_provider", "google"))
        ]
        self.speech_provider_key = str(attrs.get("speech_provider_key", ""))
        self.speech_voice = str(attrs.get("speech_voice", "DWRB4weeqtqHSoQLvPTd"))
        self.speech_generation_config = attrs.get(
            "speech_generation_config",
            {"voice_id": self.speech_voice}
            if self.speech_provider == "elevenlabs"
            else {"lang": "en", "slow": False},
        )
        self.completion_provider = CompletionProvider[
            str(attrs.get("completion_provider", "openai"))
        ]
        self.completion_model = str(attrs.get("completion_model", "gpt-4o"))
        self.completion_provider_org = str(attrs.get("completion_provider_org", ""))
        self.completion_provider_key = str(attrs.get("completion_provider_key", ""))
        if self.completion_provider == "openai":
            openai.api_key = self.completion_provider_key
            openai.organization = self.completion_provider_org
        self.completion_persona = str(attrs.get("completion_persona", ""))
        self.stt_provider = str(attrs.get("stt_provider", "google"))
        self.stt_provider_config = attrs.get(
            "stt_provider_config", self.stt_provider_config
        )
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
        self.listen_trigger_all = bool(attrs.get("listen_trigger_all", False))
        self.listen_command_buffer_length = int(
            attrs.get("listen_command_buffer_length", 10)
        )
        self.cache_ahead_completions = bool(attrs.get("cache_ahead_completions", False))
        self.disable_mic = bool(attrs.get("disable_mic", False))
        self.disable_audioout = bool(attrs.get("disable_audioout", False))
        self.use_vosk_vad = bool(
            attrs.get("use_vosk_vad", False)
        )  # New option for Vosk VAD
        self.command_list = []
        self.trigger_active = False
        self.active_trigger_type = ""
        self.stt = None

        # Fuzzy matching configuration
        self.listen_trigger_fuzzy_matching = bool(
            attrs.get("listen_trigger_fuzzy_matching", False)
        )
        self.listen_trigger_fuzzy_threshold = int(
            attrs.get("listen_trigger_fuzzy_threshold", 2)
        )
        self.save_failed_audio = bool(attrs.get("save_failed_audio", False))
        self.use_new_listener = bool(attrs.get("use_new_listener", False))
        self.stt_timeout = int(attrs.get("stt_timeout", 7))
        self.vad_config = attrs.get("vad_config", {"type": "energy"})
        self.listen_sample_rate = int(attrs.get("listen_sample_rate", 48000))

        # Stop any existing VAD
        if rec_state.listen_closer is not None:
            rec_state.listen_closer(True)
        self.stop_vosk_vad()

        # Validate threshold
        if not 0 <= self.listen_trigger_fuzzy_threshold <= 5:
            self.logger.warning(
                f"Invalid fuzzy threshold {self.listen_trigger_fuzzy_threshold}, using default 2"
            )
            self.listen_trigger_fuzzy_threshold = 2

        # Initialize fuzzy matcher if enabled
        if self.listen_trigger_fuzzy_matching:
            try:
                from src.speech.fuzzy_matcher import FuzzyWakeWordMatcher

                self.fuzzy_matcher = FuzzyWakeWordMatcher(
                    threshold=self.listen_trigger_fuzzy_threshold
                )
                self.logger.debug(
                    f"Fuzzy matching enabled with threshold={self.listen_trigger_fuzzy_threshold}"
                )
            except ImportError as e:
                self.logger.error(f"Failed to initialize fuzzy matcher: {e}")
                self.logger.warning("Falling back to regex matching")
                self.listen_trigger_fuzzy_matching = False
                self.fuzzy_matcher = None
        else:
            self.fuzzy_matcher = None

        if (
            self.speech_provider == SpeechProvider.elevenlabs
            and self.speech_provider_key != ""
        ):
            self.eleven_client["client"] = ElevenLabs(api_key=self.speech_provider_key)
        else:
            self.speech_provider = SpeechProvider.google

        if "google" not in self.stt_provider:
            stt = dependencies[SpeechService.get_resource_name(self.stt_provider)]
            self.stt = cast(SpeechService, stt)

        if not self.disable_audioout:
            if not mixer.get_init():
                try:
                    mixer.init(buffer=1024)
                except Exception as err:
                    os.environ["PULSE_SERVER"] = "/run/user/1000/pulse/native"
                    mixer.init(buffer=1024)
        else:
            if mixer.get_init():
                mixer.quit()

        rec_state.rec = sr.Recognizer()
        rec_state.rec.operation_timeout = self.stt_timeout

        if not self.disable_mic:
            # Set up speech recognition
            rec_state.rec.dynamic_energy_threshold = True

            mics = sr.Microphone.list_microphone_names()

            if self.mic_device_name != "":
                rec_state.mic = sr.Microphone(
                    device_index=mics.index(self.mic_device_name),
                    sample_rate=self.listen_sample_rate,
                )
            else:
                rec_state.mic = sr.Microphone(sample_rate=self.listen_sample_rate)

            with rec_state.mic as source:
                rec_state.rec.adjust_for_ambient_noise(source, 2)

            # set up background listening if desired
            if self.should_listen:
                self.logger.debug("Will listen in background")

                # Try Vosk VAD first if enabled
                if self.use_vosk_vad and self.start_vosk_vad():
                    self.logger.debug("Using Vosk VAD for voice activity detection")
                elif self.use_new_listener:
                    vad_type = self.vad_config.get("type")
                    vad_kwargs = self.vad_config.copy()
                    vad_kwargs.pop("type", None)
                    vad = None

                    if vad_type == "energy":
                        vad = EnergyVAD(**vad_kwargs)
                    elif vad_type == "webrtc":
                        vad = WebRTCVAD(**vad_kwargs)
                    elif vad_type == "silero":
                        vad = SileroVAD(**vad_kwargs)

                    self.logger.debug(
                        f"Using new listener with vad: {self.vad_config.get('type')}"
                    )
                    self.listener = Listener(
                        source=SpeechRecognitionSource(rec_state.mic),
                        vad=vad,
                        on_error=lambda err: self.logger.error(
                            f"new listener error: {err}"
                        ),
                        on_speech=lambda segment: self.listen_callback(
                            None,
                            sr.AudioData(
                                segment.audio_data,
                                segment.sample_rate,
                                segment.sample_width,
                            ),
                        ),
                    )

                    def pipeline_closer(wait_for_stop=True):
                        self.listener.stop()

                    rec_state.listen_closer = pipeline_closer
                    self.listener.start()
                else:
                    # Fall back to speech_recognition VAD
                    self.logger.debug("Using speech_recognition VAD")
                    rec_state.listen_closer = rec_state.rec.listen_in_background(
                        source=rec_state.mic,
                        phrase_time_limit=self.listen_phrase_time_limit,
                        callback=self.listen_callback,
                    )

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Mapping[str, ValueTypes]:
        if cmd := command.get("command"):
            if cmd == "stop_playback":
                stopped = await self.stop_playback()
                return {"command": cmd, "stopped": stopped}
        return {"status": "unknown command"}

    async def close(self):
        if rec_state.listen_closer is not None:
            rec_state.listen_closer(True)
        self.stop_vosk_vad()


def save_audio(audio_data, filename):
    """Save AudioData to WAV file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(audio_data.sample_width)
        wf.setframerate(audio_data.sample_rate)
        wf.writeframes(audio_data.get_raw_data())
