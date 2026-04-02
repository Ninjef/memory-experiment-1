"""Random fun name generator for output run folders."""

from __future__ import annotations

import random
from pathlib import Path

ADJECTIVES = [
    "chunky", "wobbly", "fuzzy", "snappy", "bubbly",
    "crispy", "squishy", "zappy", "bouncy", "goofy",
    "spicy", "toasty", "dizzy", "peppy", "quirky",
    "groovy", "sparkly", "breezy", "sassy", "zippy",
    "tangy", "fluffy", "jazzy", "nifty", "plucky",
    "snazzy", "wacky", "zesty", "perky", "jolly",
    "frothy", "gritty", "mellow", "nimble", "wiggly",
    "cosmic", "rusty", "turbo", "golden", "cheeky",
    "lunar", "swift", "mighty", "tiny", "wild",
    "lazy", "bold", "mega", "hyper", "cozy","wonky",
    "bonky", "sloppy", "glitzy", "boingy", "swoopy", 
    "clunky", "dorky", "frizzy", "pokey", "squeaky",
    "loopy", "jiggly", "nutty", "pudgy", "dingy",
    "snorty", "blinky", "dopey", "cranky"
]

NOUNS = [
    "cakepop", "noodle", "waffle", "pickle", "muffin",
    "pretzel", "taco", "biscuit", "dumpling", "pancake",
    "nugget", "turnip", "walrus", "badger", "penguin",
    "otter", "narwhal", "toucan", "puffin", "gecko",
    "comet", "nebula", "quasar", "photon", "meteor",
    "pixel", "widget", "sprocket", "gadget", "piston",
    "banjo", "kazoo", "ukulele", "cymbal", "bongo",
    "cobalt", "marble", "fossil", "cactus", "acorn",
    "tornado", "thunder", "blizzard", "geyser", "ripple",
    "doodle", "zigzag", "rascal", "trinket", "bobbin",
    "snickerdoodle", "meatball", "cupcake", "jellybean", "popcorn",
    "gizmo", "doohickey", "whirligig", "toadstool", "hubbub",
    "crumpet", "skillet", "platypus", "chipmunk", "goober",
    "moonbeam", "dinglehopper", "kerfuffle", "pebble", "snorkel"
]


def generate_run_name(output_dir: Path, timestamp: str) -> str:
    """Generate a fun run folder name like ``run_20260401_230402_chunky-cakepop``.

    If the name already exists in *output_dir*, appends ``_2``, ``_3``, etc.
    """
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    base = f"run_{timestamp}_{adj}-{noun}"

    candidate = base
    counter = 2
    while (output_dir / candidate).exists():
        candidate = f"{base}_{counter}"
        counter += 1

    return candidate
