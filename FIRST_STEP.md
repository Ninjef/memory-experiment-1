# Introduction
The first step is to set up an environment where we can easily test and iterate on different memory processing ideas.

# Methods
There is a basic input/output structure to any memory processing system.

1. What goes in? A bunch of text data, either with or without timestamps, and pre-chunked into any number of sections (for document dbs, there'd probably be one text chunk per document. For chat logs, there'd probably be one text chunk per turn of the conversation, etc...). We should also allow this data to come in with flexible metadata like timestamps, etc... not prescribed, just existing in other columns that the in-between process can leverage if I know the text coming in contains certain metadata and I want to experiment on it.
2. What's the black box in-between? The novel process runs on the text data and does whatever it's programmed to do with them. But for this first step, I want this to be a pre-existing, known effective method used for generating new insights from sets of text.
3. What comes out? We'll change this over time. But for now all that we expect to come out are more text chunks. These will be new "memories" or "insights" derived from the text chunks which were fed in, and may have other metadata associated with them (flexible). This may be a csv (if that makes sense, otherwise come up with a better idea)

# Expectations
I expect that once the first step is completed, I will A. have an example of the data structure that needs to be fed in (likely a .csv with certain columns? Choose something better if it exists) containing the input text so that I can find data online and process the fields to fit the new schema, B. Be able to run the known process for doing this kind of processing and see the output results, and C. Be able to see the new text insights that were created.

# Considerations
- This should be done in python, with a venv at the root of the directory
- LLM calls can be made to anthropic, with a comment holding the specific model names for the latest opus, sonnet, and haiku models, that can be used for easy swapping betweeen models
- There should be a .env.example file to help me know what environment variables to supply for this to work
- In the future, we will need the framework to be pliable enough to allow us to add post-processing testing methods on the resulting new memory sets. Don't make this framework so rigid that it's too tightly coupled to my assumptions here to change
