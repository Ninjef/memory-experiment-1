# Overview
We need to know whether the `projection.py` approach of steering the vector space ahead of clustering is better than the approach of simply supplying a theme and grabbing the nearest neighbors to that theme as the clusters we use. We need another `clusterer.py` approach, and therefore it seems we should have a folder for `clusterers` just like we do for `prompts` and `steerers`. Perhaps we should have a default clusterer named `default_clusterer.py` in there, which will simply be a replica of `clusterer.py`, and be used if no other clusterer is specified. Then we also need to build the new clusterer - which will require a "theme" in its args.

# Considerations
- The `projection.py` steerer has an alpha for how strong the steering is. What would be the equivalent for the new clusterer method? Would we amplify the theme somehow? Is there even a thing we could grab from that?

# Notes (archived for this task - for reference only)

We're at a crossroads now, and I need to figure out what makes most sense to do next. Here are the current issues:
1. It's hard to know whether the insights generated are real and true or just accurate-sounding - so we need to be able to verify that some way
2. I THINK it might make sense to make it possible for me to supply text for chunking up (in the `data` folder, perhaps under a folder named "unstructured text" or something). That way I can take a topic I actually know a lot about (perhaps "me"), and jam a ton of text into there that can get chunked up into snippets for generating embeddings with.
3. We haven't tested whether clustering around the vector that is used for a theme is as good as the embedding math approach used by the `projection.py` steerer (in `./src/steerers`) - we need to test that.

