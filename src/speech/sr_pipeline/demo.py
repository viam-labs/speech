#!/usr/bin/env python3
"""
Demo script for sr_pipeline POC.

Validates three-thread architecture prevents audio drops during transcription.
Run on MacOS and Raspberry Pi to compare performance.
"""

import speech_recognition as sr
import time
from .pipeline import AudioPipeline


def main():
    """Run the demo pipeline."""
    print("=" * 60)
    print("SR Pipeline POC - Three-Thread Architecture Demo")
    print("=" * 60)

    # Setup
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    # Calibrate for ambient noise
    print("\nCalibrating for ambient noise...")
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
    except OSError as e:
        print(f"❌ Error: Could not access microphone: {e}")
        print("\nTroubleshooting:")
        print("  - Check microphone is connected")
        print("  - MacOS: Check System Preferences > Security & Privacy > Microphone")
        print("  - Raspberry Pi: Check 'arecord -l' shows devices")
        return 1

    print(f"✓ Energy threshold: {recognizer.energy_threshold:.1f}")

    # Create pipeline
    def on_transcript(text: str, utt):
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
    print("Listening... (Ctrl+C to stop)")
    print("=" * 60)
    print()

    pipeline.start()

    try:
        while True:
            time.sleep(5)
            m = pipeline.metrics
            print(
                f"Stats: captured={m.chunks_captured}, dropped={m.chunks_dropped} ({m.drop_rate:.1%}), utterances={m.utterances_detected}/{m.utterances_transcribed}"
            )
    except KeyboardInterrupt:
        print("\n\nStopping...")
        pipeline.stop()

    # Final stats
    m = pipeline.metrics
    print("\n" + "=" * 60)
    print("Final Statistics")
    print("=" * 60)
    print(f"Chunks captured:        {m.chunks_captured}")
    print(f"Chunks dropped:         {m.chunks_dropped} ({m.drop_rate:.1%})")
    print(f"Utterances detected:    {m.utterances_detected}")
    print(f"Utterances transcribed: {m.utterances_transcribed}")
    print(f"Transcription errors:   {m.transcription_errors}")

    # Success criteria check
    print("\n" + "=" * 60)
    print("POC Validation")
    print("=" * 60)

    if m.drop_rate < 0.01:  # <1%
        print(f"✓ Drop rate {m.drop_rate:.1%} < 1% - SUCCESS")
    else:
        print(f"✗ Drop rate {m.drop_rate:.1%} >= 1% - NEEDS INVESTIGATION")

    if m.utterances_transcribed > 0:
        print(f"✓ {m.utterances_transcribed} utterances transcribed - SUCCESS")
    else:
        print("⚠ No utterances transcribed - try speaking louder or check network")

    return 0


if __name__ == "__main__":
    exit(main())
