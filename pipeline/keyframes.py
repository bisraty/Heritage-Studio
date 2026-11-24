"""Generate character-reference options and storyboard keyframes with FLUX."""

import argparse
import os
from time import perf_counter

from dotenv import load_dotenv
import yaml

from pipeline.narration import load_project
from pipeline.providers import cloudflare_image, post_image_form
from pipeline.utils import CacheIndex, http_status, input_hash, log_run, retry, write_artifact
from pipeline.validate import ROOT


class Keyframes:
    def __init__(self, root, config, storyboard):
        self.root = root
        self.config = config
        self.storyboard = storyboard
        self.settings = config["keyframes"]
        self.provider = config["providers"]["keyframes"]
        self.outputs = root / config["paths"]["outputs"]
        self.cache = CacheIndex(root / config["paths"]["cache_index"])
        self.log = root / config["paths"]["run_log"]
        self.golden = root / self.settings["golden_reference"]

    def get_image(self, stage, identifier, prompt, seed, width, height, references=(), *, cached_only=False):
        model = self.provider["model"]
        fields = {"prompt": prompt, "seed": seed, "width": width, "height": height}
        digest = input_hash(
            {"model": model, "endpoint": self.provider["endpoint"], "fields": fields},
            files=references,
        )
        image = self.cache.lookup(stage, identifier, digest)
        if cached_only:
            if image is None:
                label = "Reference option" if stage == "references" else "Keyframe for shot"
                raise ValueError(f"{label} {identifier} is missing. Run the {stage} stage first.")
            return image
        event = dict(
            stage=stage, shot_id=identifier if stage == "keyframes" else None,
            model=model, params=fields, seed=seed, digest=digest,
        )
        if image is not None:
            log_run(self.log, **event, status="cache_hit", cache_hit=True)
            return image

        load_dotenv(self.root / ".env")
        account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        if not account or not token:
            raise ValueError("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env")
        endpoint = self.provider["endpoint"].format(account_id=account, model=model)
        headers = {"Authorization": f"Bearer {token}"}
        images = [reference.read_bytes() for reference in references]
        if any(not image.startswith(b"\xff\xd8\xff") for image in images):
            raise ValueError("Keyframe references must be JPEG images under 512×512 pixels")

        def request_image():
            start = perf_counter()
            try:
                response = post_image_form(endpoint, headers, fields, images, self.provider["timeout_s"])
                data = cloudflare_image(response)
            except Exception as error:
                log_run(self.log, **event, status="failed", latency_s=perf_counter() - start, error=error)
                raise
            log_run(self.log, **event, status="ok", latency_s=perf_counter() - start)
            return data

        try:
            data = retry(request_image, max_attempts=self.config["retry"]["max_attempts"])
        except Exception as error:
            status = http_status(error)
            detail = f"HTTP {status}" if status else type(error).__name__
            raise ValueError(f"{stage} item {identifier} failed ({detail})") from None
        output = self.outputs / stage / f"{identifier}_{digest}.jpg"
        write_artifact(output, data)
        self.cache.record(stage, identifier, digest, output)
        return output

    def prompt(self, *parts):
        return "\n".join((*parts, self.storyboard["style_prompt"], self.storyboard["character_prompt"]))

    def reference_option(self, option, *, cached_only=False):
        reference = self.storyboard["character_reference"]
        size = self.settings["reference_size"]
        return self.get_image(
            "references", option, self.prompt(reference["prompt"]),
            reference["seeds"][option - 1], size, size, cached_only=cached_only,
        )

    def select_reference(self, option):
        image = self.reference_option(option, cached_only=True)
        write_artifact(self.golden, image.read_bytes())
        return self.golden

    def generate(self, shot_id=None, *, cached_only=False):
        shots = [shot for shot in self.storyboard["shots"] if shot_id is None or shot["id"] == shot_id]
        if not shots:
            raise ValueError(f"Storyboard has no shot {shot_id}")
        if not self.golden.is_file():
            raise ValueError("Choose a golden reference first with --select-reference 1, 2, 3, or 4")
        continuity = self.storyboard["character_reference"]["continuity_prompt"]
        artifacts = []
        for shot in shots:
            references = list(dict.fromkeys([self.golden, *(self.root / path for path in shot["references"])]))
            if len(references) > 4:
                raise ValueError(f"Shot {shot['id']} supports up to three additional reference images")
            image = self.get_image(
                "keyframes", shot["id"], self.prompt(shot["image_prompt"], continuity),
                shot["seed"], self.settings["width"], self.settings["height"], references,
                cached_only=cached_only,
            )
            artifacts.append(image)
            print(f"Shot {shot['id']}: {image}")
        return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument("--reference-options", action="store_true")
    commands.add_argument("--select-reference", type=int, choices=range(1, 5), metavar="N")
    commands.add_argument("--shot", type=int, help="Generate only this shot ID")
    args = parser.parse_args()
    try:
        config, storyboard = load_project(ROOT)
        if "character_reference" not in storyboard:
            raise ValueError("Set character_reference in storyboard.json before running the keyframe stage")
        keyframes = Keyframes(ROOT, config, storyboard)
        if args.reference_options:
            for option in range(1, 5):
                print(f"Option {option}: {keyframes.reference_option(option)}")
        elif args.select_reference:
            print(f"Golden reference: {keyframes.select_reference(args.select_reference)}")
        else:
            keyframes.generate(args.shot)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
