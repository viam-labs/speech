# speech modular service

*speech* is a modular service that provides text-to-speech (TTS) and speech-to-text(STT) capabilities for robots running on the Viam platform.

This module implements the [Speech Service API (`viam-labs:service:speech`)](https://github.com/viam-labs/speech-service-api). See the documentation for that service to learn more about using it with the Viam SDKs.

## Prerequisites

On Linux:

`run.sh` will automatically install the following system dependencies if not already set up on the machine:

- python3-pyaudio
- portaudio19-dev
- alsa-tools
- alsa-utils
- flac

On MacOS:

``` bash
brew install portaudio
```

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

*enum - "openai" (default: "openai")*

Other providers may be supported in the future.  [completion_provider_org](#completion_provider_org) and [completion_provider_key](#completion_provider_key) must also be provided.

### completion_model

*enum - "gpt-4|gpt-3.5-turbo" (default: "gpt-4")*

Other models may be supported in the future.  [completion_provider_org](#completion_provider_org) and [completion_provider_key](#completion_provider_key) must also be provided.

### completion_provider_org

*string (default: "")*

### completion_provider_key

*string (default: "")*

### completion_persona

*string (default: "")*

If set, will pass "As <completion_persona> respond to '<completion_text>'" to all completion() requests.

### listen

*boolean (default: false)*

If set to true and the robot as an available microphone device, will enable listening in the background.

If enabled, it will respond to configured [listen_trigger_say](#listen_trigger_say), [listen_trigger_completion](#listen_trigger_completion) and [listen_trigger_command](#listen_trigger_command), based on input audio being converted to text.

If *listen* is enabled and [listen_triggers_active](#listen_triggers_active) is disabled, triggers will occur when [listen_trigger](#listen_trigger) is called.

Note that background (ambient) noise and microphone quality are important factors in the quality of the STT conversion.
Currently, Google STT is leveraged.

### listen_phrase_time_limit

*float (default: None)*

The maximum number of seconds that this will allow a phrase to continue before stopping and returning the part of the phrase processed before the time limit was reached.
The resulting audio will be the phrase cut off at the time limit.
If phrase_timeout is None, there will be no phrase time limit.
Note: if you are seeing instance where phrases are not being returned for much longer than you expect, try changing this to ~5 or so.

### listen_trigger_say

*string (default: "robot say")*

If *listen* is true, any audio converted to text that is prefixed with *listen_trigger_say* will be converted to speech and repeated back by the robot.

### listen_trigger_completion

*string (default: "hey robot")*

If *listen* is true, any audio converted to text that is prefixed with *listen_trigger_completion* will be sent to the completion provider (if configured), converted to speech, and repeated back by the robot.

### listen_trigger_command

*string (default: "robot can you")*

If [listen](#listen) is true, any audio converted to text that is prefixed with *listen_trigger_command* will be stored in a LIFO buffer (list of strings) of size [listen_command_buffer_length](#listen_command_buffer_length) that can be retrieved via [get_commands()](#get_commandsinteger), enabling programmatic voice control of the robot.

### listen_command_buffer_length

*integer (default: 10)*

### mic_device_name

*string (default: "")*

If not set, will attempt to use the first available microphone device.
If set, will attempt to use a specifically labeled device name.
Available microphone device names will logged on module startup.

### cache_ahead_completions

*boolean (default: false)*

If true, will read a second completion for the request and cache it for next time a matching request is made.
This is useful for faster completions when completion text is less variable.

### disable_mic

*boolean (default: false)*

If true, will not configure any listening capabilities.
This must be set to true if you do not have a valid microphone attached to your system.

## Troubleshooting

When using a USB audio device, it may sometimes come up as the default, sometimes not.
To ensure that it comes up consistently as the default, there are a couple things you can try:

### Using an alsa config file

1. Run `aplay -l`, you will see output similar to:

```
**** List of PLAYBACK Hardware Devices ****
card 1: rockchipdp0 [rockchip-dp0], device 0: rockchip-dp0 spdif-hifi-0 [rockchip-dp0 spdif-hifi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 2: rockchiphdmi0 [rockchip-hdmi0], device 0: rockchip-hdmi0 i2s-hifi-0 [rockchip-hdmi0 i2s-hifi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 3: rockchipes8388 [rockchip-es8388], device 0: dailink-multicodecs ES8323 HiFi-0 [dailink-multicodecs ES8323 HiFi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 4: UACDemoV10 [UACDemoV1.0], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

Identify the device card number you wish to use for output.
In our example, we'll use the USB audio device (card 4).
As root, add the following to `/etc/asound.conf`

```
defaults.pcm.card 4
defaults.ctl.card 4
```

### Using a modprobe config file

1. check the existing alsa modules:

```
cat /proc/asound/modules
```

This will output something like:

```
 0 snd_usb_audio
 2 snd_soc_meson_card_utils
 3 snd_usb_audio
```

2. ensure the USB device comes up first by editing /etc/modprobe.d/alsa-base.conf, adding content similar to:

```
options snd slots=snd-usb-audio,snd_soc_meson_card_utils
```
