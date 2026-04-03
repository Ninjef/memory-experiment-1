# Overview

We need to implement part 4 of "## Zero-Shot Latent Space Steering Idea" in @IDEA_OVERVIEW.md. Currently we go straight to step 5. I want this to be flexible enough to enable plug-and-play of different python implementations (probably per-file)

# Considerations
- We need to be able to swap out different ways of doing step 4. It should be possible to NOT do step 4 with the CLI as well
- If possible and it makes sense for the goal I'm trying to achieve (easy way to test different methods), I'd like each approach to be stored in its own python file / folder / however big it needs to be, within this repository, to make it easy to swap methods
- One idea is to force the person running the CLI to specify the file name of the python file which should run step 4
- - However, there might need to be CLI arguments for the file that runs step 4 - if so, please give me an idea for how to deal with this and still preserve modularity
- If possible, I'd also like the clustering algorithm to be configurable
