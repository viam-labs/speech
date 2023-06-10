# speech modular service

*speech* is a modular service that provides text-to-speech (TTS) and speech-to-text(STT) capabilties for robots running on the Viam platform.

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
Commands would exist in the buffer if *listen* is configured and the robot has heard any commands (triggered by *listen_trigger_command*)

## Configuration

The following attributes may be configured as speech service config attributes.

### speech_provider

**enum - "google"|"elevenlabs" (default: "google")**


### speech_provider_key

**string (default: "")**

### speech_voice

**string (default: "")**

### speech_voice

**string (default: "")**

