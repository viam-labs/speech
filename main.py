import asyncio

from viam.module.module import Module

from src.speech.speechio import SpeechIOService
from src.discovery import DiscoverDevices

if __name__ == "__main__":
    asyncio.run(Module.run_from_registry())
