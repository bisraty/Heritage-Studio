"""HTTP requests and response decoding for the configured model providers."""

from base64 import b64decode
import json
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


class ProviderResponseError(ValueError):
    """A provider returned a response without a usable result."""


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_json(endpoint, headers, payload, timeout_s):
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    return read_response(request, timeout_s)


def read_response(request, timeout_s):
    with build_opener(RejectRedirects()).open(request, timeout=timeout_s) as response:
        return json.load(response)


def post_image_form(endpoint, headers, fields, references, timeout_s):
    boundary = uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
            .encode("utf-8")
        )
    for index, reference in enumerate(references):
        parts.extend([
            (f'--{boundary}\r\nContent-Disposition: form-data; name="input_image_{index}"; '
             'filename="reference.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode("ascii"),
            reference,
            b"\r\n",
        ])
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    request = Request(
        endpoint, data=b"".join(parts), method="POST",
        headers={**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return read_response(request, timeout_s)


def gemini_text(response):
    for candidate in response.get("candidates", []):
        text = "".join(
            part.get("text", "")
            for part in candidate.get("content", {}).get("parts", [])
            if not part.get("thought")
        )
        if text.strip():
            return text
    raise ProviderResponseError("Gemini returned no text")


def speech_request(model, text, voice, *, style=None):
    content = {"type": "text", "text": text}
    if style:
        content["annotations"] = [{"type": "speech_metadata", "style": style}]
    return {
        "model": model,
        "input": [{"type": "user_input", "content": [content]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }


def gemini_audio(response):
    for step in reversed(response.get("steps", [])):
        if step.get("type") == "model_output":
            for part in reversed(step.get("content", [])):
                if part.get("type") == "audio":
                    audio = b64decode(part.get("data", ""), validate=True)
                    if len(audio) > 44 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE":
                        return audio
    raise ProviderResponseError("Gemini returned no WAV audio")


def cloudflare_image(response):
    if response.get("success") is True:
        image = b64decode(response.get("result", {}).get("image", ""), validate=True)
        if image.startswith(b"\xff\xd8\xff") and image.endswith(b"\xff\xd9"):
            return image
    raise ProviderResponseError("Cloudflare returned no JPEG image")
