# `speech` modular service

*speech* is a modular service that provides text-to-speech (TTS) and speech-to-text (STT) capabilities for machines running on the Viam platform.

This module implements the [Speech Service API (`viam-labs:service:speech`)](https://github.com/viam-labs/speech-service-api). See the documentation for that API to learn more about using it with the Viam SDKs.

## Requirements

On Linux:

`build.sh` will automatically include the following system dependencies as part of the PyInstaller executable:

- `python3-pyaudio`
- `portaudio19-dev`
- `alsa-tools`
- `alsa-utils`
- `flac`

On MacOS, `build.sh` will include the following dependencies using [Homebrew](https://brew.sh):

*** As a note, pyaudio's dependency on portaudio requires python3.11. However, the required package distils is deprecated in this version, so environments will need to install setuptools instead ***
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
  "speech_generation_config": {},
  "speech_voice": "<VOICE-OPTION>",
  "completion_provider": "openai",
  "completion_model": "gpt-4|gpt-3.5-turbo",
  "completion_provider_org": "<org-abc123>",
  "completion_provider_key": "<sk-mykey>",
  "completion_persona": "<PERSONA>",
  "listen": true,
  "stt_provider": "google",
  "stt_provider_config": {},
  "use_vosk_vad": false,
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
| `speech_generation_config`  | object | Optional | This can be used to configure a built-in Text-to-Speech provider ("google" or "elevenlabs"). See more details in the full README.  |
| `completion_provider`  | string | Optional | `"openai"`. Other providers may be supported in the future. [completion_provider_org](#completion_provider_org) and [completion_provider_key](#completion_provider_key) must also be provided. Default: `"openai"`. |
| `completion_model`  | string | Optional | `gpt-4o`, `gpt-4o-mini`, etc. [completion_provider_org](#completion_provider_org) and [completion_provider_key](#completion_provider_key) must also be provided. Default: `"gpt-4o"`. |
| `completion_provider_org`  | string | Optional | Your org for the completion provider. Default: `""`. |
| `completion_provider_key`  | string | Optional | Your key for the completion provider. Default: `""`. |
| `completion_persona`  | string | Optional | If set, will pass "As <completion_persona> respond to '<completion_text>'" to all completion() requests. Default: `""`. |
| `listen`  | boolean | Optional | If set to true and the robot as an available microphone device, will enable listening in the background.<br><br>If enabled, it will respond to configured [listen_trigger_say](#listen_trigger_say), [listen_trigger_completion](#listen_trigger_completion) and [listen_trigger_command](#listen_trigger_command), based on input audio being converted to text.<br><br>If *listen* is enabled and [listen_triggers_active](#listen_triggers_active) is disabled, triggers will occur when [listen_trigger](#listen_trigger) is called.<br><br>Note that background (ambient) noise and microphone quality are important factors in the quality of the STT conversion.<br><br>Currently, Google STT is leveraged. Default: `false`. |
| `stt_provider`  | string | Optional | This can be set to the name of a configured speech service that provides a `to_text` command, like [`stt-vosk`](https://app.viam.com/module/viam-labs/stt-vosk)\*. Or set it to "google_cloud" to use the Google Cloud Speech-to-Text API. Otherwise, the Google STT API will be used. Default: `"google"`. |
| `stt_provider_config`  | object | Optional | This can be used to configure a built-in Speech-to-Text provider ("google" or "google_cloud"). See more details in the full README.  |
| `listen_phrase_time_limit`  | float | Optional | The maximum number of seconds that this will allow a phrase to continue before stopping and returning the part of the phrase processed before the time limit was reached.<br><br>The resulting audio will be the phrase cut off at the time limit.<br><br>If phrase_timeout is None, there will be no phrase time limit.<br><br>Note: if you are seeing instance where phrases are not being returned for much longer than you expect, try changing this to ~5 or so. **Works with both default VAD and Vosk VAD.** Default: `None`. |
| `listen_trigger_say`  | string | Optional | If *listen* is true, any audio converted to text that is prefixed with *listen_trigger_say* will be converted to speech and repeated back by the robot. Default: `"robot say"`. |
| `listen_trigger_completion`  | string | Optional | If *listen* is true, any audio converted to text that is prefixed with *listen_trigger_completion* will be sent to the completion provider (if configured), converted to speech, and repeated back by the robot. Default: `"hey robot"`. |
| `listen_trigger_command`  | string | Optional |  If `"listen": true`, any audio converted to text that is prefixed with *listen_trigger_command* will be stored in a LIFO buffer (list of strings) of size [listen_command_buffer_length](#listen_command_buffer_length) that can be retrieved via [get_commands()](https://github.com/viam-labs/speech-service-api/blob/main/README.md#get_commandsinteger) from the Speech Service API, enabling programmatic voice control of the robot. Default: `"robot can you"`. |
| `listen_command_buffer_length`  | integer | Optional | The buffer length for the command. Default: `10`. |
| `mic_device_name`  | string | Optional | If not set, will attempt to use the first available microphone device.<br><br>If set, will attempt to use a specifically labeled device name.<br><br>Available microphone device names will logged on module startup. Default: `""`. |
| `cache_ahead_completions`  | boolean | Optional | If true, will read a second completion for the request and cache it for next time a matching request is made. This is useful for faster completions when completion text is less variable. Default: `false`. |
| `disable_mic`  | boolean | Optional | If true, will not configure any listening capabilities. This must be set to true if you do not have a valid microphone attached to your system. Default: `false`. |
| `disable_audioout`  | boolean | Optional | If true, will not configure any audio output capabilities. This must be set to true if you do not have a valid audio output device attached to your system. Default: `false`. |
| `use_vosk_vad`  | boolean | Optional | If true, will use Vosk for Voice Activity Detection (VAD) instead of the default speech_recognition VAD. The Vosk model will be automatically downloaded (~40MB) on first use. Default: `false`. |


### Example configuration

The following configuration sets up listening mode with local speech-to-text, uses an ElevenLabs voice "Antoni", makes AI completions available, and uses a 'Gollum' persona for AI completions:

``` json
{
  "completion_provider_org": "org-abc123",
  "completion_provider_key": "sk-mykey",
  "completion_persona": "Gollum",
  "listen": true,
  "stt_provider": "google",
  "speech_provider": "elevenlabs",
  "speech_provider_key": "keygoeshere",
  "speech_voice": "Antoni",
  "mic_device_name": "myMic"
}
```

## Do Commands

The speech module supports the following `do_command` methods:

### `stop_playback`

Immediately stop any current audio playback.

```json
{
    "command": "stop_playback"
}
```

## Voice Activity Detection (VAD)

The speech service supports two Voice Activity Detection systems:

### Default VAD (speech_recognition)
- Uses the built-in VAD from the `speech_recognition` library
- Good for basic voice detection
- Works out of the box with no additional setup

### Vosk VAD
- **Better handling of background noise**
- **More precise speech boundary detection**
- **Automatic model downloading** (~40MB) on first use
- **Fallback protection** - automatically uses default VAD if Vosk fails
- **Phrase time limiting** - respects `listen_phrase_time_limit` parameter

#### Enabling Vosk VAD
To use Vosk VAD, simply set `"use_vosk_vad": true` in your configuration. The system will:

1. **Automatically download** the Vosk model on first use
2. **Extract and verify** the model
3. **Start Vosk VAD**
4. **Fall back gracefully** to default VAD if anything fails


## Fuzzy Wake Word Matching

The speech service supports fuzzy matching for wake word detection using Levenshtein distance (edit distance) via the rapidfuzz library. This improves accuracy when speech recognition produces slight variations while preventing partial-word false positives.

### Enabling Fuzzy Matching

To enable fuzzy wake word matching, add to your configuration:

```json
{
  "listen_trigger_fuzzy_matching": true,
  "listen_trigger_fuzzy_threshold": 2
}
```

### How It Works

Fuzzy matching uses **word-boundary matching** to allow wake words to trigger even when transcribed slightly differently, while preventing false matches:

- **"hey robot"** will match **"hey Robert"** (distance = 2) ✓
- **"robot say"** will match **"robotic say"** (distance = 2) ✓
- **"robot can you"** will match **"robot can u"** (distance = 1) ✓
- **"hey robot"** will NOT match **"they robotic"** (word boundaries prevent partial-word matches) ✗

The system automatically checks alternative transcriptions from Google Speech Recognition for better accuracy. The word-boundary approach achieves 100% accuracy in testing versus 87.5% for character-level matching.

### Configuration

| Attribute | Default | Description |
|-----------|---------|-------------|
| `listen_trigger_fuzzy_matching` | `false` | Enable/disable fuzzy matching |
| `listen_trigger_fuzzy_threshold` | `2` | Maximum edit distance (0-5). Lower = stricter matching |

### Threshold Guidelines

- **Threshold 1**: Very strict, for short wake words
- **Threshold 2-3**: Recommended for most wake words (default: 2)
- **Threshold 4-5**: Lenient, for noisy environments

### Troubleshooting

**Not triggering enough?** Increase the threshold:
```json
{"listen_trigger_fuzzy_threshold": 3}
```

**Triggering too much?** Decrease the threshold:
```json
{"listen_trigger_fuzzy_threshold": 1}
```

**Not working at all?** Check that fuzzy matching is enabled and logs don't show import errors.

## Speech-to-Text Provider Configuration

The `stt_provider_config` attribute in the speech service configuration can be used to set or override the fields on a speech recognition request to built-in providers, such as "google" and "google_cloud".

### "google" configuration

This provider sends requests to the public Google Speech Recognition API.

| Attribute | Default | Description |
|-----------|---------|-------------|
| `key` | None | Set a custom API key to be used. [Learn more about getting an API key](https://www.chromium.org/developers/how-tos/api-keys/) |
| `language` | `en-US` | Set the language for the transcription. [Available options here](https://stackoverflow.com/questions/14257598/what-are-language-codes-in-chromes-implementation-of-the-html5-speech-recogniti/14302134#14302134) |
| `pfilter` | 0 | Adjust the profanity filer: 0 - no filter, 1 - only show the first character and replace the rest with astericks |

### "google_cloud" configuration

This provider sends requests to the Google Cloud Speech-to-Text API V1.

| Attribute | Default | Description |
|-----------|---------|-------------|
| `credentials_json_path` | None | File path to the [service account key configuration](https://cloud.google.com/docs/authentication/set-up-adc-local-dev-environment#local-key) to be used to authenticate with Google Cloud. The service account required the Service Usage Consumer role. [Learn more](https://docs.cloud.google.com/speech-to-text/docs/v1/transcribe-client-libraries) |
| `language_code` | `"en-US"` | Set the language for the transcription. [Available options here](https://stackoverflow.com/questions/14257598/what-are-language-codes-in-chromes-implementation-of-the-html5-speech-recogniti/14302134#14302134) |
| `model` | `"default"` | Which transcription model to use. [See options here](https://cloud.google.com/speech-to-text/docs/reference/rest/v1/RecognitionConfig) |
| `use_enhanced` | `false` | Set to `true` to use an "enhanced" speech recognition model. This can only be used in combination with the `"phone_call"` or `"video"` model selection. |
| `preferred_phrases` | None | Provide a list of strings containing words or phrases "hints" so the speech recognition is more likely to recognize them. |

## Text-to-Speech Generation Configuration

The `speech_generation_config` attribute in the speech service configuration can be used to set or override the fields on a speech generation request to built-in providers, such as "google" and "elevenlabs".

### "google" configuration

This provider sends requests to the public Google Translate's Text-to-Speech API

| Attribute | Default | Description |
|-----------|---------|-------------|
| `lang` | `"en"` | Set the language for the generated speech. [Available options here](https://en.wikipedia.org/wiki/IETF_language_tag#List_of_common_primary_language_subtags) |
| `slow` | `false` | Reads text more slowly. |

### "elevenlabs" configuration

This provider sends requests to ElevenLabs' Text-to-Speech API

| Attribute | Default | Description |
|-----------|---------|-------------|
| `voice_id` | `"DWRB4weeqtqHSoQLvPTd"` (Josh) | ID for voice from [voice library](https://elevenlabs.io/app/voice-library) |
| `model_id` | `"eleven_multilingual_v2"` | Set the model for the generation. [Available options here](https://elevenlabs.io/docs/overview/models) |


## Configure the `discovery service`

This service queries the device for available microphone devices to be used for text-to-speech services.

The output from this discovery can be used to configure a `viam-labs:speech:speechio` service.

If an expected device doesn't appear, try following the troubleshooting steps in the module README.

### Configuration
The following attribute template can be used to configure this model:

```json
{
}
```

#### Attributes

The following attributes are available for this model:

| Name          | Type   | Inclusion | Description                |
|---------------|--------|-----------|----------------------------|

#### Example Configuration

```json
{
}
```

# Troubleshooting 
## ALSA Configuration Guide for Speechio Service

## Overview

The speechio service requires specific ALSA configuration to work properly with USB microphones and audio output devices. This guide provides step-by-step instructions for setting up persistent ALSA configuration that survives machine reboots.

## Key Requirements

- **Speechio service needs 16000Hz sample rate** for speech recognition
- **USB microphones typically run at 44100Hz** (some at 48000Hz)
- **Rate conversion is required** using ALSA `plug` plugin
- **Configuration must persist across reboots**

## Step-by-Step Setup

### 1. Identify Your Audio Hardware

First, identify your audio devices:

```bash
# List playback devices
aplay -l

# List capture devices  
arecord -l

# Check current card assignments
cat /proc/asound/cards
```

**Typical setup:**
- **Audio output device**: Usually card 0 (speakers/DAC)
- **USB Microphone**: Usually card 1 (microphone input)

### 2. Test Current Configuration

Test if you get rate conversion warnings:

```bash
# Test recording at 16000Hz (required by speechio)
arecord -f S16_LE -r 16000 -c 1 -t wav /tmp/test_default.wav &
sleep 3
kill %1
```

**Common issue:** `Warning: rate is not accurate (requested = 16000Hz, got = 44100Hz)`

### 3. Create Persistent ALSA Configuration

**⚠️ Important: Use device names, not card numbers, for reliability across reboots**

First, find your device names:
```bash
# Find device names (more stable than card numbers)
cat /proc/asound/cards
```

Then create `/etc/asound.conf` using device names:

```bash
sudo tee /etc/asound.conf > /dev/null << 'EOF'
# ALSA Configuration for Speechio Service
# Uses device names for stability across reboots

pcm.!default {
    type asym
    playback.pcm {
        type hw
        card YourOutputDevice    # Replace with your audio output device name
        device 0
    }
    capture.pcm {
        type plug               # CRITICAL: Use plug for rate conversion
        slave.pcm {
            type hw
            card YourMicDevice  # Replace with your USB microphone device name
            device 0
        }
    }
}

ctl.!default {
    type hw
    card YourOutputDevice
}
EOF
```


### 4. Test the Configuration

Verify rate conversion works without warnings:

```bash
# Test recording - should work without rate warnings
arecord -f S16_LE -r 16000 -c 1 -t wav /tmp/test_fixed.wav &
sleep 3
kill %1

# Test playback
speaker-test -D default -t wav -c 2 -l 1
```

**Expected result:** No rate conversion warnings

### 6. Verify Configuration Persistence

Ensure the configuration will survive reboots:

```bash
# Check that the file is not managed by packages
dpkg -S /etc/asound.conf 2>/dev/null || echo "✓ File not managed by packages (good)"

# Verify file exists and has correct content
cat /etc/asound.conf
```

**Expected logs:**
- `"Will listen in background"` - Service initialized
- `"speechio heard audio"` - Audio detected when you speak
- `"speechio heard <text>"` - Speech successfully transcribed


## Troubleshooting Common Issues

### Issue: Rate Conversion Warnings
**Symptom:** `Warning: rate is not accurate (requested = 16000Hz, got = 44100Hz)`

**Solution:** Use `type plug` for capture device in `/etc/asound.conf`

### Issue: No Audio Detected by Speechio
**Symptom:** No "speechio heard audio" logs when speaking

**Solution:** 
1. Verify microphone with `arecord -l`
2. Check ALSA configuration with `arecord -D default -f S16_LE -r 16000 -c 1 -t wav /tmp/test.wav`
3. Ensure `/etc/asound.conf` uses correct device names

### Issue: Configuration Resets After Reboot
**Symptom:** Audio setup works until machine restarts

**Solution:** 
1. Use `/etc/asound.conf` (not `~/.asoundrc`)
2. Verify file is not managed by packages: `dpkg -S /etc/asound.conf`
3. Check file permissions: `sudo chmod 644 /etc/asound.conf`

### Issue: Wrong Audio Device Selected / Card Numbers Change
**Symptom:** Speechio uses wrong microphone or speaker, or stops working after reboot

**Cause:** Card numbers (0, 1, 2) can change between reboots based on USB detection order

**Solution:** Use device names instead of card numbers in `/etc/asound.conf`

```bash
# Find stable device names
cat /proc/asound/cards

# Example output:
# 0 [sndrpihifiberry]: HifiBerry-DAC - HifiBerry DAC
# 1 [Device        ]: USB-Audio - USB PnP Sound Device

# Use device names in config:
card sndrpihifiberry    # Instead of card 0
card Device             # Instead of card 1
```

## Testing Checklist

Before deploying speechio service:

- [ ] Audio devices detected: `aplay -l` and `arecord -l`
- [ ] Rate conversion works: `arecord -f S16_LE -r 16000 -c 1 -t wav /tmp/test.wav` (no warnings)
- [ ] ALSA config persists: `/etc/asound.conf` exists and not package-managed
- [ ] Speechio logs show: "Will listen in background"
- [ ] Speaking generates: "speechio heard audio" logs
- [ ] Configuration survives reboot

## Advanced Configuration Options

### Using modprobe for Consistent Card Numbers

If you prefer to use card numbers instead of device names, you can ensure consistent card ordering:

1. **Check existing ALSA modules:**
```bash
cat /proc/asound/modules
```

**Example output:**
```
0 snd_usb_audio
2 snd_soc_meson_card_utils
3 snd_usb_audio
```

2. **Set module loading order:**
```bash
sudo tee /etc/modprobe.d/alsa-base.conf > /dev/null << 'EOF'
# Ensure USB audio devices load first
options snd slots=snd-usb-audio,snd_soc_meson_card_utils
EOF
```

3. **Use card numbers in ALSA config:**
```bash
sudo tee /etc/asound.conf > /dev/null << 'EOF'
pcm.!default {
    type asym
    playback.pcm "plughw:0,0"    # First USB device
    capture.pcm "plughw:0,0"     # Same device for capture
}
EOF
```

**Note:** Device names are still recommended over this approach for better stability.

## Notes for Developers

- The `plug` plugin automatically handles rate conversion (44100Hz → 16000Hz)
- Device names are more stable than card numbers across reboots
- System-wide configuration (`/etc/asound.conf`) is required for viam-server access
- Restart viam-server after ALSA configuration changes (speechio reinitializes audio devices on service restart)
- Test thoroughly before deploying to multiple devices
