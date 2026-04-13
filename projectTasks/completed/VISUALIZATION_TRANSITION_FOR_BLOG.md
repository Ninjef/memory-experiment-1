# Overview

I am writing a blog about the experimentation done in this repo. I need to be able to give readers a solid visualization of what's happening as I steer the embedding space based on a theme.

To do so, I want to be able to base the clusters of a visualization on either the visualization in question, or on another run's clustering of the same embeddings. If another run's clustering, I want the colors to be the exact same for each cluster, and the cluster members to remain the same as well.

# Considerations:
- I want a new clustering approach that can be supplied to the command line. It will simply take the path of another output file and mirror the clustering done in that file
- If some text embedding ids from the base output don't exist in the new output, throw a warning to the terminal and ignore them. Same if some text embeddings in the new output don't exist in the base output.
