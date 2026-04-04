# Overview

Currently it takes awhile to load the embedding model every time, and generate embeddings every time for all the source texts, and even the theme, when we already know the embeddings for each. We should cache embeddings for source text and for theme texts when steering. If those exact texts have already gotten an embedding, we simply load it up. If not, only THEN do we spin up the embedding model and generate new embeddings, and cache those newly generated embeddings in the same way; by exact text of the embedding.
