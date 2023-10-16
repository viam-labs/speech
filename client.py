import asyncio
import os

from src.speech import SpeechService

from viam import logging
from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions

# these must be set, you can get them from your robot's 'CODE SAMPLE' tab
robot_secret = os.getenv('ROBOT_SECRET') or ''
robot_address = os.getenv('ROBOT_ADDRESS') or ''

async def connect():
    creds = Credentials(type="robot-location-secret", payload=robot_secret)
    opts = RobotClient.Options(refresh_interval=0, dial_options=DialOptions(credentials=creds), log_level=logging.DEBUG)
    return await RobotClient.at_address(robot_address, opts)


async def main():
    robot = await connect()

    print("Resources:")
    print(robot.resource_names)

    speech = SpeechService.from_robot(robot, name="speechio")

    text = await speech.say("Good day, friend!", True)
    print(f"The robot said '{text}'")

    # note: this will fail unless you have a completion provider configured
    text = await speech.completion("Give me a quote one might say if they were saying 'Good day, friend!'", False)
    print(f"The robot said '{text}'")

    # note: this will fail unless you have a completion provider configured
    #text = await speech.completion("Give me a quote one might say regarding this robots resources: " 
    #                               + str(robot.resource_names) + " using documentation at https://docs.viam.com as reference")
    #print(f"The robot said '{text}'")

    is_speaking = await speech.is_speaking()
    print(is_speaking)

    commands = await speech.get_commands(2)
    print(str(commands))
    
    await robot.close()


if __name__ == "__main__":
    asyncio.run(main())