# Cloud services: opt-in, named, logged

Everything runs locally unless the user names a provider for this video. A provider runs only when the
project's `brief.json` lists it in `cloud_allow`, and every request goes through `cloud.py`. A key in the
environment is never permission: `GEMINI_API_KEY`, `ELEVENLABS_API_KEY` and the rest are usually set on a
developer's machine, and a set key caused the Gemini frame leak in the trials.

## Permission

- Read the user's words for this video. "Use ElevenLabs for the voice" names `elevenlabs`. "Add stock
  footage" names a category, not a provider: ask which one (`pexels` or `pixabay`) before going on.
- Put the named providers in the brief when the project is created, from a brief file:
  `{"cloud_allow": ["elevenlabs"]}` passed as
  `python3 "$SKILL_DIR/scripts/studio.py" project new --slug S --product P --brief-json brief.json`.
  An unknown name is rejected. Add a provider later only when the user names it, and record that by
  editing `cloud_allow` in `brief.json`.
- Default `cloud_allow` is empty. With it empty, voices come from Kokoro, visuals are built in code, and
  no stock or generated media is fetched.
- A named provider does not carry over to the next video, and it does not change the brand. The saved
  brand voice stays as it is unless the user asks to save the new one.
- When a call fails because the key variable is unset, tell the user which variable to export. Do not ask
  them to paste a key into the chat or write one into a file.

## Making a call

```bash
python3 "$SKILL_DIR/scripts/cloud.py" call --project "$PROJECT" --provider pexels --method GET \
  --url "https://api.pexels.com/v1/videos/search?query=terminal&per_page=5"
python3 "$SKILL_DIR/scripts/cloud.py" call --project "$PROJECT" --provider elevenlabs --method POST \
  --url "https://api.elevenlabs.io/v1/text-to-speech/<voice_id>" --json body.json --out "$PROJECT/assets/voice/a.mp3"
```

- `--provider` is one of `elevenlabs`, `openai`, `pexels`, `pixabay`, `freesound`; `--method` is `GET` or `POST`.
- `--json` takes a file path or inline JSON. Without `--out` the JSON result carries a text `preview` of
  the first 2000 characters; with `--out` the body is written to that file.
- Output is one JSON object: `{"status", "out", "bytes"}` (plus `preview` or `error`). Exit 1 means refused
  or failed: provider not in `cloud_allow`, key variable unset, a host or scheme the provider does not
  allow, a redirect elsewhere, an HTTP error. Exit 2 is a usage error.
- The script reads the key from the provider's environment variable, sends it in the provider's header
  (or, for Pixabay, a `key` query parameter) and only to the provider's API host, never to its CDN. It
  never prints or logs the key. Do not add auth headers or keys to the URL or body yourself.
- Only `https` URLs on the provider's own hosts are accepted. Never call a provider with `curl` or
  Python directly, even for a download.
- Every attempted request appends `ts, provider, method, host, path, status, bytes` to
  `$PROJECT/calls.jsonl`. `verify.py` checks that every logged provider is in `cloud_allow`, and the review
  page lists the calls. That file is the audit; do not edit it.
- Save downloads under `$PROJECT/assets/` (`voice/`, `music/`, `stock/`, `images/`).

## Providers

| Provider | Use it for | Endpoint (script adds auth) | Key variable |
|---|---|---|---|
| `elevenlabs` | a cloud narration voice | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`; body `{"text", "model_id"}`; MP3 by default | `ELEVENLABS_API_KEY` |
| `openai` | a cloud narration voice; generated still images | `POST https://api.openai.com/v1/audio/speech`; `POST https://api.openai.com/v1/images/generations` | `OPENAI_API_KEY` |
| `pexels` | stock video and photos | `GET https://api.pexels.com/v1/videos/search?query=`, `GET .../v1/search?query=`; files come from `videos.pexels.com` and `images.pexels.com` | `PEXELS_API_KEY` |
| `pixabay` | stock video and images | `GET https://pixabay.com/api/videos/?q=`, `GET https://pixabay.com/api/?q=`; files come from `cdn.pixabay.com` | `PIXABAY_API_KEY` |
| `freesound` | sound effects and music beds | `GET https://freesound.org/apiv2/search/text/?query=&fields=id,name,license,username,previews,duration`; previews come from `cdn.freesound.org` | `FREESOUND_API_KEY` |

Endpoint and field details are from the providers' docs as read on 2026-10-22; model ids change fast
(DALL-E 2 and 3 were retired in May 2026), so read an error response before assuming a model name is wrong.

- A cloud voice replaces Kokoro for that video. Save the speech to `assets/voice/<id>.mp3`, convert it to
  `assets/voice/<id>.wav` with ffmpeg, then run `voice.py align` and `voice.py captions` as in
  [audio.md](audio.md). Phoneme patches do not apply to cloud voices; respell the word. `voice.py say`
  refuses a non-Kokoro brand voice.
- OpenAI speech: send `{"model", "input", "voice", "response_format": "wav"}`. Input is at most 4096
  characters. `instructions` works only with `gpt-4o-mini-tts`.
- OpenAI images: save the response with `--out` and read the saved JSON for the image data. Use them as
  stills the storyboard shows; label them as AI-generated where the terms ask.
- Freesound originals need OAuth2, which `cloud.py` does not do. Use the `previews` URLs
  (`preview-hq-mp3`) and keep the sound's `license` and `username`.
- Free-tier limits are small (Pexels about 200 requests an hour, Pixabay 100 per minute). Search once,
  pick, download; do not loop.

## Licences and attribution

Write one line per downloaded or generated asset to `$PROJECT/assets/attribution.md`: file, provider,
author or voice, licence, source URL, date. Put the credit lines on the end card or in the delivery note.

| Service | Rule |
|---|---|
| ElevenLabs | Free plan output cannot be used commercially and needs attribution ("elevenlabs.io" or "11.ai" in the title). Paid plans include a commercial licence. Ask the user which plan they are on. [source](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform) |
| OpenAI | The usage policies ask you to tell viewers a synthetic voice is AI-generated; say so in the end card or description. This rests on a search snippet, because the primary page returned 403 when researched. Generated images: keep prompt, model id and date. |
| Pexels | Free to use and modify, credit appreciated but not required. Do not sell unaltered copies, imply endorsement, show identifiable people in a bad light, or redistribute on other stock sites. [licence](https://www.pexels.com/license/) |
| Pixabay | Free to use and modify without attribution. Do not sell or distribute unchanged content, or use it misleadingly, especially recognisable people. [licence](https://pixabay.com/service/license-summary/) |
| Freesound | Each sound has its own licence. CC0 needs no credit. Attribution (CC-BY) requires credit to the author. NonCommercial rules the sound out for a commercial video. Prefer CC0 or CC-BY and record the licence with the file. [API docs](https://freesound.org/docs/api/resources_apiv2.html) |

Credit line for a CC-BY sound: `"<name>" by <username>, CC BY, via Freesound`.

## Not offered

- Gemini frame review. Claude reviews the frames decoded from the MP4 itself, so a Gemini pass would
  duplicate that and add a cloud call. `hf.py` strips Gemini and Google keys from every HyperFrames call
  and forces `snapshot --describe false`, because `snapshot` otherwise sends frames to Gemini whenever a
  key is present.
- Generated video. `cloud.py` accepts no video-generation provider in v1: model names and shutdowns churn
  (Google's Veo 3.1 Preview was shut down on the day this was researched) and the jobs are asynchronous.
  If the user asks, say it is not supported yet and offer stock video from a named provider, a generated
  still with motion built in code, or a Blender scene ([3d.md](3d.md)).
