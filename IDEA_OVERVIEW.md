# Overview
The industry needs AI to have better memory. Right now memory is episodic; what do the chat logs say? What does the doc say? There are techniques to graduate memory from episodic memory to higher-level insight, but they don't seem adequate yet. They will be discussed briefly below.

AI can only find meaningful insights between seemingly unrelated text if it sees all those texts together and uses its intelligence to deduce insights that can be built upon. For example, if it has the following text snippets in its memory:

"User: Spoons are better than forks dude... you can always use a spoon to kinda' spear and pick things up, but you can't ever ever use a fork to drink soup. I've got lots of spoons," and "User: I need to work on my budget, we're really spending too much lately." For those examples, a modern AI could intelligently deduce that the user may be too focused on buying many unnecessary items, like extra spoons, and perhaps issues with prioritizing purchases could underlie their financial problems.

However, the AI probably won't look up those two memories simultaneously. When the user mentions the budget again, the AI's RAG will find the budget concern. And when the user talks about silverware, they'll bring up the spoon debacle. But those two memories will likely never come together unless the user specifically discusses both spoons and budget closely together.

With the current approach to AI memory, the user must bridge ideas for the AI. The AI has no methods to bridge ideas itself.

People are trying to manifest this kind of meta-knowledge and insight in different ways. One of my favorite approaches is periodically having a different process cluster the raw text embeddings using various methods, then calling an LLM to generate higher level summaries (RAPTOR Rag system does this for documentation). But this suffers from a similar issue to the original. The clustering is likley to only cluster ideas that have high similarity, like budget and finances, and spoons and silverware. The AI is still unlikely to see the ideas together.

My idea is to mimic human dreaming as I see it, through what I'm tentatively calling "Zero-Shot Latent Space Steering."

There is a periodic, offline batch process in the memory framework. Here are the steps:

## Zero-Shot Latent Space Steering Idea

1. An LLM "dream director" generates specific thematic concepts, for example: "financial anxieties," "tech stack preferences," "food and budget," etc...
2. We generate an embedding for each of these in the same way raw text embeddings are generated.
note: We cannot multiply these embeddings directly to the existing memory embeddings because they are dense. We have to instead figure out what the common components of the dream theme vectors are. 
3. We calculate the projection of each memory embedding on each theme embedding, and isolate that component from the "rest" of the memory - the parts that don't match the theme at all.
4. We crank up the intensity of those parts of the vector that relate to the theme, then recombine the rest of the vector into it to get a version of the embedding where the Dream Director's theme is outsized now.
5. We feed these new, distored vectors, into UMAP and HDBSCAN, for clustering memories. The outsized theme component will force previously less related concepts to be more likely to cluster together.
6. An LLM uses the clustered memories to form new insights / reflections, etc... Other methods already in use are applied (much like they are in the claude code memory management repo) to help manage these new insights as useful memories.