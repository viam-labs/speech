# speech modular service

*speech* is a modular service that provides text-to-speech (TTS) and speech-to-text(STT) capabilities for robots running on the Viam platform.

## Prerequisites

``` bash
sudo apt update && sudo apt upgrade -y
sudo apt-get install python3
sudo apt install python3-pip
sudo apt install python3-pyaudio
sudo apt-get install alsa-tools alsa-utils
sudo apt-get install flac
```

On MacOS:

``` bash
brew install portaudio
```

## API

The speech resource provides the following API:

### say(*string*)

The *say()* command takes a string, and converts to speech audio that is played back on the robot, provided it has an audio output (speaker) device attached.
It returns a string response, which is the string that was passed in to the *say()* request.


### completion(*string*)

The *completion()* command takes a string, sends that to an AI LLM completion provider (if configured) and converts the returned completion to speech audio that is played back on the robot, provided it has an audio output (speaker) device attached.
It returns a string response, which is the completion returned from the completion provider.

### get_commands(*integer*)

The *get_commands()* command takes an integer representing the number of commands to return, and returns that number of commands as a list of strings from the FIFO command buffer, removing them from that buffer at the time of return.
Commands will exist in the buffer if [listen](#listen) is configured and the robot has heard any commands (triggered by [listen_trigger_command](#listen_trigger_command)).
This enables voice-activated programmatic control of the robot.

## Viam Service Configuration

The following attributes may be configured as speech service config attributes.
For example: the following configuration would set up listening mode, use an ElevenLabs voice "Antoni", make AI completions available, and use a 'Gollum' persona for AI completions:

``` json
{
  "completion_provider_org": "org-abc123",
  "completion_provider_key": "sk-mykey",
  "completion_persona": "Gollum",
  "listen": true,
  "speech_provider": "elevenlabs",
  "speech_provider_key": "keygoeshere",
  "speech_voice": "Antoni",
  "mic_device_name": "myMic"
}
```

### speech_provider

*enum - "google"|"elevenlabs" (default: "google")*

### speech_provider_key

*string (default: "")*

### speech_voice

*string (default: "Josh")*

If the speech_provider (example: elevenlabs) provides voice options, the voice can be selected here.

### completion_provider

*enum - "openaigpt35turbo" (default: "openaigpt35turbo")*

Other providers may be supported in the future.  [completion_provider_org](#completion_provider_org) and [completion_provider_key](#completion_provider_key) must also be provided.

### completion_provider_org

*string (default: "")*

### completion_provider_key

*string (default: "")*

### completion_persona

*string (default: "")*

If set, will pass "As <completion_persona> respond to '<completion_text>'" to all completion() requests.

### mic_device_name

*string (default: "")*

If set, will attempt to use a specifically labeled device name.  If not set, will use system default mic device.

### listen

*boolean (default: False)*

If set to True and the robot as an available microphone device, will listen and respond to [listen_trigger_say](#listen_trigger_say), [listen_trigger_completion](#listen_trigger_completion) and [listen_trigger_command](#listen_trigger_command), based on input audio being converted to text.
Note that background (ambient) noise and microphone quailty are important factors in the quality of the STT conversion.
Currently, Google STT is leveraged.

### listen_trigger_say

*string (default: "robot say")*

If *listen* is True, any audio converted to text that is prefixed with *listen_trigger_say* will be converted to speech and repeated back by the robot.

### listen_trigger_completion

*string (default: "hey robot")*

If *listen* is True, any audio converted to text that is prefixed with *listen_trigger_completion* will be sent to the completion provider (if configured), converted to speech, and repeated back by the robot.

### listen_trigger_command

*string (default: "robot can you")*

If [listen](#listen) is True, any audio converted to text that is prefixed with *listen_trigger_command* will be stored in a LIFO buffer (list of strings) of size [listen_command_buffer_length](#listen_command_buffer_length) that can be retrieved via [get_commands()](#get_commandsinteger), enabling programmatic voice control of the robot.

### listen_command_buffer_length

*integer (default: 10)*

### mic_device_name

*string (default: "")*

If not set, will attempt to use the first available microphone device.
Available microphone device names will logged on module startup.

## Using speech with the Python SDK

Because this module uses a custom protobuf-based API, you must include this project in your client code.  One way to do this is to include it in your requirements.txt as follows:

```
audioout @ git+https://github.com/viam-labs/speech.git@main
```

You can now import and use it in your code as follows:

```
from speech import SpeechService
speech = SpeechService.from_robot(robot, name="speech")
speech.say(...)
