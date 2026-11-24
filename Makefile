PYTHON ?= python
FFMPEG ?= ffmpeg
FFPROBE ?= ffprobe
WORKDIR ?= $(CURDIR)
WORKDIR_ARG = --workdir "$(WORKDIR)"
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
	$(VENV_PYTHON) -m pipeline.validate $(WORKDIR_ARG)

smoke:
	$(VENV_PYTHON) -m pipeline.smoke $(WORKDIR_ARG)

stage:
ifeq ($(S),narration)
	$(VENV_PYTHON) -m pipeline.narration $(WORKDIR_ARG)
else ifeq ($(S),keyframes)
	$(VENV_PYTHON) -m pipeline.keyframes $(WORKDIR_ARG)
else ifeq ($(S),shots)
	$(VENV_PYTHON) -m pipeline.shots $(WORKDIR_ARG) --ffmpeg "$(FFMPEG)"
else ifeq ($(S),music)
	$(VENV_PYTHON) -m pipeline.music $(WORKDIR_ARG)
else ifeq ($(S),assemble)
	$(VENV_PYTHON) -m pipeline.assemble $(WORKDIR_ARG) --cached-only --ffmpeg "$(FFMPEG)" --ffprobe "$(FFPROBE)"
else
	$(error Supported stages: narration, keyframes, shots, music and assemble)
endif

narration:
	$(VENV_PYTHON) -m pipeline.narration $(WORKDIR_ARG)

radio:
	$(VENV_PYTHON) -m pipeline.radio $(WORKDIR_ARG) --ffmpeg "$(FFMPEG)"

keyframes:
	$(VENV_PYTHON) -m pipeline.keyframes $(WORKDIR_ARG)

references:
	$(VENV_PYTHON) -m pipeline.keyframes $(WORKDIR_ARG) --reference-options

reference:
	$(VENV_PYTHON) -m pipeline.keyframes $(WORKDIR_ARG) --select-reference "$(N)"

shots:
	$(VENV_PYTHON) -m pipeline.shots $(WORKDIR_ARG) --ffmpeg "$(FFMPEG)"

music:
	$(VENV_PYTHON) -m pipeline.music $(WORKDIR_ARG)

film:
	$(VENV_PYTHON) -m pipeline.assemble $(WORKDIR_ARG) --ffmpeg "$(FFMPEG)" --ffprobe "$(FFPROBE)"

shot:
	$(VENV_PYTHON) -m pipeline.assemble $(WORKDIR_ARG) --shot "$(ID)" --ffmpeg "$(FFMPEG)" --ffprobe "$(FFPROBE)"

check-tools:
	$(PYTHON) --version
	$(FFMPEG) -version
	$(FFPROBE) -version
