import asyncio

from viam.module.module import Module
from viam.resource.registry import Registry, ResourceCreatorRegistration

from src.speech.speechio import SpeechIOService, SpeechService


async def main():
    """This function creates and starts a new module, after adding all desired resources.
    Resources must be pre-registered. For an example, see the `gizmo.__init__.py` file.
    """
    Registry.register_resource_creator(
        SpeechService.API,
        SpeechIOService.MODEL,
        ResourceCreatorRegistration(SpeechIOService.new),
    )

    module = Module.from_args()
    module.add_model_from_registry(SpeechService.API, SpeechIOService.MODEL)
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
