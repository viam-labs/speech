"""Three-thread audio pipeline for speech recognition."""

import threading
import queue
import time
import collections
from logging import Logger
from typing import Any, Callable, Dict, Optional
import speech_recognition as sr

from .types import AudioChunk, Utterance, PipelineMetrics
from .energy_vad import EnergyVAD


# Type aliases for callbacks
TranscriptCallback = Callable[[str, Utterance], None]
UtteranceCallback = Callable[[Utterance], None]
ErrorCallback = Callable[[Exception], None]


# Hardcoded POC configuration
ENERGY_THRESHOLD = 300.0
SILENCE_TIMEOUT = 0.8  # seconds
SPEECH_PADDING = 0.3  # seconds
MAX_SPEECH_DURATION = 30.0  # seconds
FRAME_DURATION_MS = 30  # milliseconds
CAPTURE_QUEUE_SIZE = 100
UTTERANCE_QUEUE_SIZE = 10


class AudioPipeline:
    """
    Decoupled audio capture and processing pipeline.

    Separates capture, VAD/segmentation, and transcription into independent
    threads to prevent audio drops during transcription.
    """

    def __init__(
        self,
        recognizer: sr.Recognizer,
        source: sr.Microphone,
        logger: Logger,
        on_transcript: Optional[TranscriptCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        on_utterance: Optional[UtteranceCallback] = None,
        recognizer_options: Dict[str, Any] = {},
    ):
        """
        Initialize AudioPipeline.

        Args:
            recognizer: speech_recognition Recognizer instance
            source: speech_recognition Microphone instance
            on_transcript: Callback for transcription results (text, utterance)
            on_error: Optional callback for errors
        """
        self.recognizer = recognizer
        self.recognizer_options = recognizer_options
        self.source = source
        self.on_transcript = on_transcript
        self.on_utterance = on_utterance
        self.on_error = on_error or self._default_error_handler
        self.logger = logger

        # VAD setup
        self.vad = EnergyVAD(threshold=recognizer.energy_threshold)

        # Queues
        self._capture_queue: queue.Queue[Optional[AudioChunk]] = queue.Queue(
            maxsize=CAPTURE_QUEUE_SIZE
        )
        self._utterance_queue: queue.Queue[Optional[Utterance]] = queue.Queue(
            maxsize=UTTERANCE_QUEUE_SIZE
        )

        # Control
        self._running = False
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

        # Metrics
        self.metrics = PipelineMetrics()

    def _default_error_handler(self, e: Exception) -> None:
        """Default error handler that prints to console."""
        self.logger.error(f"Pipeline error: {e}")

    def start(self) -> None:
        """Start all pipeline threads."""
        self.logger.debug("Starting audio pipeline")
        if self._running:
            raise RuntimeError("Pipeline already running")

        self._running = True
        self._stop_event.clear()

        self._threads = [
            threading.Thread(
                target=self._capture_loop, name="sr-pipeline-capture", daemon=True
            ),
            threading.Thread(
                target=self._detect_loop, name="sr-pipeline-detect", daemon=True
            ),
            threading.Thread(
                target=self._transcribe_loop, name="sr-pipeline-transcribe", daemon=True
            ),
        ]

        self.logger.debug("Starting threads")
        for t in self._threads:
            t.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop all pipeline threads gracefully."""
        self.logger.debug("Stopping audio pipeline")
        if not self._running:
            self.logger.debug("Pipeline not running")
            return

        self._running = False
        self._stop_event.set()

        # Send poison pills to unblock queue.get()
        try:
            self.logger.debug("Stopping capture queue")
            self._capture_queue.put_nowait(None)
        except queue.Full:
            pass

        try:
            self.logger.debug("Stopping utterance queue")
            self._utterance_queue.put_nowait(None)
        except queue.Full:
            pass

        # Wait for threads
        self.logger.debug("Stopping threads")
        for t in self._threads:
            t.join(timeout=timeout)

        self._threads.clear()

    def wait(self) -> None:
        """Block until stop() is called or threads exit."""
        while self._running and any(t.is_alive() for t in self._threads):
            time.sleep(0.1)

    def _capture_loop(self) -> None:
        """
        Dedicated capture thread.

        Reads audio chunks at fixed intervals, never blocks on downstream.
        CRITICAL: Uses put_nowait() to never block - drops frames if queue full.
        """
        chunk_samples = int(self.source.SAMPLE_RATE * FRAME_DURATION_MS / 1000)

        with self.source as s:
            while self._running:
                try:
                    # Read audio - releases GIL during device read
                    data = s.stream.read(chunk_samples)

                    chunk = AudioChunk(
                        data=data,
                        timestamp=time.monotonic(),
                        sample_rate=s.SAMPLE_RATE,
                        sample_width=s.SAMPLE_WIDTH,
                    )

                    # Non-blocking put - NEVER block capture thread
                    try:
                        self._capture_queue.put_nowait(chunk)
                        self.metrics.chunks_captured += 1
                    except queue.Full:
                        # Drop frame and track metric
                        self.metrics.chunks_dropped += 1

                except OSError as e:
                    # Audio device error - fatal
                    if self._running:
                        self.on_error(e)
                    break
                except Exception as e:
                    if self._running:
                        self.on_error(e)

    def _detect_loop(self) -> None:
        """
        VAD and utterance segmentation thread.

        Implements simplified 2-state FSM:
        - IDLE: Wait for speech, maintain padding buffer
        - SPEAKING: Accumulate audio, emit after silence timeout
        """
        # State: "idle" or "speaking"
        state = "idle"

        # Ring buffer for speech padding
        padding_frames = int(SPEECH_PADDING * 1000 / FRAME_DURATION_MS)
        padding_buffer: collections.deque[AudioChunk] = collections.deque(
            maxlen=max(1, padding_frames)
        )

        # Utterance accumulator
        utterance_chunks: list[AudioChunk] = []
        speech_start_time: Optional[float] = None
        last_speech_time: Optional[float] = None

        while self._running:
            try:
                chunk = self._capture_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if chunk is None:  # Poison pill
                break

            # Run VAD
            try:
                self.logger.debug("Checking audio for voice activity")
                vad_result = self.vad.process(chunk)
            except Exception as e:
                self.on_error(e)
                continue

            is_speech = vad_result.is_speech
            now = chunk.timestamp

            # FSM transitions
            if state == "idle":
                padding_buffer.append(chunk)
                if is_speech:
                    self.logger.debug("Voice activity detected")
                    # Start speaking
                    state = "speaking"
                    speech_start_time = now
                    last_speech_time = now
                    utterance_chunks = list(padding_buffer)

            elif state == "speaking":
                utterance_chunks.append(chunk)
                if is_speech:
                    last_speech_time = now

                # Check if we should emit utterance
                silence_duration = now - last_speech_time
                speech_duration = now - speech_start_time

                if silence_duration >= SILENCE_TIMEOUT:
                    # Silence timeout - emit utterance
                    self.logger.debug("Silence detected")
                    self._emit_utterance(utterance_chunks, speech_start_time, now)
                    state = "idle"
                    utterance_chunks = []
                    padding_buffer.clear()
                    self.vad.reset()
                elif speech_duration >= MAX_SPEECH_DURATION:
                    self.logger.debug("Hit max speech duration")
                    # Max duration - force emit
                    self._emit_utterance(utterance_chunks, speech_start_time, now)
                    state = "idle"
                    utterance_chunks = []
                    padding_buffer.clear()
                    self.vad.reset()

    def _emit_utterance(
        self, chunks: list[AudioChunk], start: float, end: float
    ) -> None:
        """Package chunks as Utterance and queue for transcription."""
        if not chunks:
            return

        # Combine chunks into single audio blob
        audio_bytes = b"".join(c.data for c in chunks)
        audio_data = sr.AudioData(
            audio_bytes,
            chunks[0].sample_rate,
            chunks[0].sample_width,
        )

        utterance = Utterance(
            audio=audio_data,
            start_time=start,
            end_time=end,
        )

        try:
            self._utterance_queue.put_nowait(utterance)
            self.metrics.utterances_detected += 1
        except queue.Full:
            self.logger.warning(
                f"Utterance queue full, dropping {utterance.duration:.1f}s utterance"
            )

    def _transcribe_loop(self) -> None:
        """
        Transcription thread.

        Consumes utterances and calls Google Speech API.
        Network I/O releases the GIL - doesn't block capture.
        """
        while self._running:
            try:
                utterance = self._utterance_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if utterance is None:  # Poison pill
                break

            try:
                # Recognition - releases GIL during network I/O
                if self.on_utterance:
                    self.logger.debug("Calling on_utterance with speech audio")
                    self.on_utterance(utterance)
                    self.logger.debug("Finished processing speech audio")
                else:
                    text = self.recognizer.recognize_google(
                        utterance.audio, **self.recognizer_options
                    )

                    self.metrics.utterances_transcribed += 1

                    # Invoke callback
                    if self.on_transcript:
                        try:
                            self.on_transcript(text, utterance)
                        except Exception as e:
                            self.on_error(e)

            except sr.UnknownValueError:
                # No speech recognized - not an error, just skip
                self.logger.warning("Transcribe loop: could not recognize audio")
                pass
            except sr.RequestError as e:
                # API error - warn and continue
                self.metrics.transcription_errors += 1
                self.on_error(e)
            except Exception as e:
                self.metrics.transcription_errors += 1
                self.on_error(e)
