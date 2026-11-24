PYTHON ?= python
FFMPEG ?= ffmpeg
FFPROBE ?= ffprobe
ifeq ($(OS),Windows_NT)
VENV_PYTHON := .venv/Scripts/python.exe
else
VENV_PYTHON := .venv/bin/python
endif

.DEFAULT_GOAL := help

.PHONY: help setup check-tools validate smoke narration stage radio keyframes references reference shots music film shot

help:
	@echo make setup - check tools and install Python dependencies
	@echo make validate - validate storyboard.json
	@echo make smoke - call the text, speech, and image providers once each
	@echo make stage S=narration - generate narration WAVs
	@echo make radio - render the captioned radio cut
	@echo make references - generate four character reference options
	@echo make reference N=1 - choose a character reference option
	@echo make stage S=keyframes - generate keyframes from the selected reference
	@echo make stage S=shots - build shot clips
	@echo make stage S=music - list imported candidates and the selected score
	@echo make film - render both film exports and captions
	@echo make shot ID=5 - refresh one shot and rebuild both exports

setup: check-tools
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install -r requirements.txt

validate:
	$(VENV_PYTHON) -m pipeline.validate

smoke:
	$(VENV_PYTHON) -m pipeline.smoke

stage:
ifeq ($(S),narration)
	$(VENV_PYTHON) -m pipeline.narration
else ifeq ($(S),keyframes)
	$(VENV_PYTHON) -m pipeline.keyframes
else ifeq ($(S),shots)
	$(VENV_PYTHON) -m pipeline.shots --ffmpeg "$(FFMPEG)"
else ifeq ($(S),music)
	$(VENV_PYTHON) -m pipeline.music
else ifeq ($(S),assemble)
	$(VENV_PYTHON) -m pipeline.assemble --cached-only --ffmpeg "$(FFMPEG)" --ffprobe "$(FFPROBE)"
else
	$(error Supported stages: narration, keyframes, shots, music and assemble)
endif

narration:
	$(VENV_PYTHON) -m pipeline.narration

radio:
	$(VENV_PYTHON) -m pipeline.radio --ffmpeg "$(FFMPEG)"

keyframes:
	$(VENV_PYTHON) -m pipeline.keyframes

references:
	$(VENV_PYTHON) -m pipeline.keyframes --reference-options

reference:
	$(VENV_PYTHON) -m pipeline.keyframes --select-reference "$(N)"

shots:
	$(VENV_PYTHON) -m pipeline.shots --ffmpeg "$(FFMPEG)"

music:
	$(VENV_PYTHON) -m pipeline.music

film:
	$(VENV_PYTHON) -m pipeline.assemble --ffmpeg "$(FFMPEG)" --ffprobe "$(FFPROBE)"

shot:
	$(VENV_PYTHON) -m pipeline.assemble --shot "$(ID)" --ffmpeg "$(FFMPEG)" --ffprobe "$(FFPROBE)"

check-tools:
	$(PYTHON) --version
	$(FFMPEG) -version
	$(FFPROBE) -version
