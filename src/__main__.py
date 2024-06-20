import asyncio

from viam.module.module import Module

from speech_service_api import SpeechService
from .speech import SpeechIOService


async def main():
    """This function creates and starts a new module, after adding all desired resources.
    Resources must be pre-registered. For an example, see the `gizmo.__init__.py` file.
    """

    module = Module.from_args()
    module.add_model_from_registry(SpeechService.SUBTYPE, SpeechIOService.MODEL)
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
