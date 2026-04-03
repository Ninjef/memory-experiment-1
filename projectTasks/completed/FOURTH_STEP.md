# Overview

We now have: 1. A way to run experiments, 2. A way to visualize the results, 3. A strong set of outputs for each experiment.

# Experiment Observations
My progression of usage for this codebase have been:
1. Run basic clustering of texts using classic methods, then run the novel method, and see if clustering changes visually using the interactive 3d map. It did!
2. See if the clustering changes are predictable. Ie, if under normal clustering I have a cluster of nodes related to LGBTQ+ topics and another distant cluster of nodes related to art, then set a theme to "LGBTQ+ and the pursuit of artistic endeavors", nodes from those previously distant clusters should cluster together. This turned out to be true!
3. The hypothesis when I started was that there may be insights or ideas that can and should be gained from normally distant clusters. And that when those distant clusters suddenly become co-located, these ideas and insights can now surface. I have not yet shown this to be true. It is a hard thing to prove with the current setup, because I have to A. Generate insights manually in Anthropic, B. Read those insights to try and understand their meaning, and C. Actually know the truth about the underlying texts so I can verify if my new approach actually surfaces meaningful insights or just new ideas at random.

# Requirements
- Insights on clusters must be auto-generated via an API call to Anthropic
- Insights should be stored very closely to the texts they came from - it must be easy for me to see the insights
- In the HTML output, there should be a way to toggle on/off insights on the map
- In the HTML output, the insights themselves should be very easy to identify as insights vs clusters
- There's an issue where with large numbers of clusters, the color coding repeats so it visually looks like cluster 2 is the same cluster as cluster 17 - fix this
- A way to swap out system prompts being used for the insight generation, perhaps a library of system prompts that can simply be chosen. For now they don't have prompt variables so can just be text files (unless you find a reason for us to inject variables into them)

# Considerations
- We already have an insights.json that we generate, but since that implementation I've had a new output file: cluster_texts.json, be generated so I could manually look at what clusters were looking like. I propose keeping both. cluster_texts.json should make it easy to reference clusters visually, and perhaps even just become a text file with markdown (and clear separation of texts and sections - please use best practices for this. The texts have to be separated so it's obvious where one ends and the next one begins) to make it clear that it's not meant for coding use. And insights.json should be easy to tie back to a cluster ID, and cluster ID should be easy to tie back to text IDs (whatever those variables are actually called)
- I have been using a prompt manually to generate insights. Please include it as a prompt being used for this. It is under projectTasks/InsightGeneratingPrompt.txt