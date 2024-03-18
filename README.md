# `speech` modular service

*speech* is a modular service that provides text-to-speech (TTS) and speech-to-text (STT) capabilities for machines running on the Viam platform.

This module implements the [Speech Service API (`viam-labs:service:speech`)](https://github.com/viam-labs/speech-service-api). See the documentation for that service to learn more about using it with the Viam SDKs.

## Requirements

On Linux:

`run.sh` will automatically install the following system dependencies if not already set up on the machine:

- `python3-pyaudio`
- `portaudio19-dev`
- `alsa-tools`
- `alsa-utils`
- `flac`

On MacOS, `run.sh` will install the following dependencies using [Homebrew](https://brew.sh) before adding the modular resource:

``` bash
brew install portaudio
```

Before configuring your speech service, you must also [create a machine](https://docs.viam.com/fleet/machines/#add-a-new-machine).

## Build and run

To use this module, follow these instructions to [add a module from the Viam Registry](https://docs.viam.com/registry/configure/#add-a-modular-resource-from-the-viam-registry) and select the `viam-labs:speech:speechio` model from the [`speech` module](https://app.viam.com/module/viam-labs/speech).

## Configure your `speech service`

Navigate to the **Config** tab of your machine's page in [the Viam app](https://app.viam.com/).
Click on the **Services** subtab and click **Create service**.
Select the `speech` type, then select the `speech:speechio` model.
Click **Add module**, then enter a name for your speech service and click **Create**.

On the new component panel, copy and paste the following attribute template into your sensor’s **Attributes** box:

```json
{
  "speech_provider": "google|elevenlabs",
  "speech_provider_key": "<SECRET-KEY>",
  "speech_voice": "<VOICE-OPTION>",
  "completion_provider": "openai",
  "completion_model": "gpt-4|gpt-3.5-turbo",
  "completion_provider_org": "<org-abc123>",
  "completion_provider_key": "<sk-mykey>",
  "completion_persona": "<PERSONA>",
  "listen": true,
  "listen_provider": "google",
  "listen_trigger_say": "<TRIGGER-PHRASE>",
  "listen_trigger_completion": "<COMPLETION-PHRASE>",
  "listen_trigger_command": "<COMMAND-TO-RETRIEVE-STORED-TEXT>",
  "listen_command_buffer_length": 10,
  "listen_phrase_time_limit": 5,
  "mic_device_name": "myMic",
  "cache_ahead_completions": false,
  "disable_mic": false
}
```

> [!NOTE]
> For more information, see [Configure a Machine](https://docs.viam.com/manage/configuration/).

### Attributes

The following attributes are available for the `viam-labs:speech:speechio` speech service:

| Name    | Type   | Inclusion    | Description |
| ------- | ------ | ------------ | ----------- |
| `speech_provider` | string | Optional | The speech provider for the voice service: `"google"` or `"elevenlabs"`. Default: `"google"`.  |
| `speech_provider_key` | string | **Required** | The secret key for the provider - only required for elevenlabs. Default: `""`. |
| `speech_voice`  | string | Optional | If the speech_provider (example: elevenlabs) provides voice options, you can select the voice here. Default: `"Josh"`. |
| `completion_provider`  | string | Optional | `"openai"`. Other providers may be supported in the future. [completion_provider_org](#completion_provider_org) and [completion_provider_key](#completion_provider_key) must also be provided. Default: `"openai"`. |
| `completion_model`  | string | Optional | `gpt-4` or `gpt-3.5-turbo`. Other models may be supported in the future.  [completion_provider_org](#completion_provider_org) and [completion_provider_key](#completion_provider_key) must also be provided. Default: `"gpt-4"`. |
| `completion_provider_org`  | string | Optional | Your org for the completion provider. Default: `""`. |
| `completion_provider_key`  | string | Optional | Your key for the completion provider. Default: `""`. |
| `completion_persona`  | string | Optional | If set, will pass "As <completion_persona> respond to '<completion_text>'" to all completion() requests. Default: `""`. |
| `listen`  | boolean | Optional | If set to true and the robot as an available microphone device, will enable listening in the background.<br><br>If enabled, it will respond to configured [listen_trigger_say](#listen_trigger_say), [listen_trigger_completion](#listen_trigger_completion) and [listen_trigger_command](#listen_trigger_command), based on input audio being converted to text.<br><br>If *listen* is enabled and [listen_triggers_active](#listen_triggers_active) is disabled, triggers will occur when [listen_trigger](#listen_trigger) is called.<br><br>Note that background (ambient) noise and microphone quality are important factors in the quality of the STT conversion.<br><br>Currently, Google STT is leveraged. Default: `false`. |
| `listen_provider`  | string | Optional | This can be set to the name of a configured speech service that provides `to_text` and `listen` commands, like [`stt-vosk`](https://app.viam.com/module/viam-labs/stt-vosk). Otherwise, the Google STT API will be used. Default: `"google"`. |
| `listen_phrase_time_limit`  | float | Optional | The maximum number of seconds that this will allow a phrase to continue before stopping and returning the part of the phrase processed before the time limit was reached.<br><br>The resulting audio will be the phrase cut off at the time limit.<br><br>If phrase_timeout is None, there will be no phrase time limit.<br><br>Note: if you are seeing instance where phrases are not being returned for much longer than you expect, try changing this to ~5 or so. Default: `None`. |
| `listen_trigger_say`  | string | Optional | If *listen* is true, any audio converted to text that is prefixed with *listen_trigger_say* will be converted to speech and repeated back by the robot. Default: `"robot say"`. |
| `listen_trigger_completion`  | string | Optional | If *listen* is true, any audio converted to text that is prefixed with *listen_trigger_completion* will be sent to the completion provider (if configured), converted to speech, and repeated back by the robot. Default: `"hey robot"`. |
| `listen_trigger_command`  | string | Optional |  If `"listen": true`, any audio converted to text that is prefixed with *listen_trigger_command* will be stored in a LIFO buffer (list of strings) of size [listen_command_buffer_length](#listen_command_buffer_length) that can be retrieved via [get_commands()](#get_commandsinteger), enabling programmatic voice control of the robot. Default: `"robot can you"`. |
| `listen_command_buffer_length`  | integer | Optional | The buffer length for the command. Default: `10`. |
| `mic_device_name`  | string | Optional | If not set, will attempt to use the first available microphone device.<br><br>If set, will attempt to use a specifically labeled device name.<br><br>Available microphone device names will logged on module startup. Default: `""`. |
| `cache_ahead_completions`  | boolean | Optional | If true, will read a second completion for the request and cache it for next time a matching request is made. This is useful for faster completions when completion text is less variable. Default: `false`. |
| `disable_mic`  | boolean | Optional | If true, will not configure any listening capabilities. This must be set to true if you do not have a valid microphone attached to your system. Default: `false`. |
| `disable_audioout`  | boolean | Optional | If true, will not configure any audio output capabilities. This must be set to true if you do not have a valid audio output device attached to your system. Default: `false`. |

### Example configuration

The following configuration sets up listening mode with local speech-to-text, uses an ElevenLabs voice "Antoni", makes AI completions available, and uses a 'Gollum' persona for AI completions:

``` json
{
  "completion_provider_org": "org-abc123",
  "completion_provider_key": "sk-mykey",
  "completion_persona": "Gollum",
  "listen": true,
  "listen_provider": "stt",
  "speech_provider": "elevenlabs",
  "speech_provider_key": "keygoeshere",
  "speech_voice": "Antoni",
  "mic_device_name": "myMic"
}
```

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
