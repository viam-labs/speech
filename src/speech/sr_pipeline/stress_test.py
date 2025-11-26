#!/usr/bin/env python3
"""
Stress test for sr_pipeline POC.

Adds artificial delay to transcription to validate that capture
continues without dropping frames even when transcription is slow.
"""

import speech_recognition as sr
import time
from .pipeline import AudioPipeline


def main():
    """Run the stress test."""
    print("=" * 60)
    print("SR Pipeline POC - Stress Test")
    print("=" * 60)
    print("\nThis test adds a 2-second delay to each transcription.")
    print("Capture should continue without dropping frames.\n")

    # Setup
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    # Calibrate
    print("Calibrating for ambient noise...")
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
    except OSError as e:
        print(f"❌ Error: Could not access microphone: {e}")
        return 1

    print(f"✓ Energy threshold: {recognizer.energy_threshold:.1f}")

    # Wrap transcription callback with artificial delay
    def on_transcript(text: str, utt):
        print(f"[{utt.duration:.1f}s] Starting transcription (will take 2s)...")
        time.sleep(2)  # Simulate slow API
        print(f"[{utt.duration:.1f}s] You said: {text}")

    def on_error(e: Exception):
        print(f"⚠ Error: {e}")

    pipeline = AudioPipeline(
        recognizer=recognizer,
        source=mic,
        on_transcript=on_transcript,
        on_error=on_error,
    )

    # Start listening
    print("\n" + "=" * 60)
    print("Listening... Speak continuously for 10+ seconds")
    print("=" * 60)
    print()

    pipeline.start()

    try:
        # Run for 30 seconds
        for i in range(6):
            time.sleep(5)
            m = pipeline.metrics
            print(
                f"[{(i + 1) * 5}s] Stats: captured={m.chunks_captured}, dropped={m.chunks_dropped} ({m.drop_rate:.1%}), utterances={m.utterances_detected}/{m.utterances_transcribed}"
            )
    except KeyboardInterrupt:
        print("\n\nStopping...")

    pipeline.stop()

    # Final stats
    m = pipeline.metrics
    print("\n" + "=" * 60)
    print("Stress Test Results")
    print("=" * 60)
    print(f"Chunks captured:        {m.chunks_captured}")
    print(f"Chunks dropped:         {m.chunks_dropped} ({m.drop_rate:.1%})")
    print(f"Utterances detected:    {m.utterances_detected}")
    print(f"Utterances transcribed: {m.utterances_transcribed}")

    print("\n" + "=" * 60)
    print("Validation")
    print("=" * 60)

    if m.drop_rate < 0.01:  # <1%
        print(f"✓ Drop rate {m.drop_rate:.1%} < 1% EVEN WITH 2s DELAY - SUCCESS!")
        print("  This proves capture thread doesn't block during transcription.")
    else:
        print(f"✗ Drop rate {m.drop_rate:.1%} >= 1% - ARCHITECTURE ISSUE")

    return 0


if __name__ == "__main__":
    exit(main())
