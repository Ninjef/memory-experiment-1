# Overview

We now need to be able to run external data through this system. I've created a folder named `rawDataPreFormatted`, where I'd like to put raw data found on the web, and a python script of the same name (so it's visibly next to the existing data file), used to extract that data from that file.

# Considerations
- The script that extracts data into the needed format should output to the `data` folder, into a new folder with the name of the dataset we put in there. Below that folder, there should be the extracted jsonl data file with a timestamp in the name along with other parameters like how many records are in the file, and anything else that might be useful.
- The only script we need right now is for the only file in @rawDataPreFormatted, which is currently locomo10.json
- The script should consider bringing in all unstructured data from the source file, like user speaking, response or ai speaking, questions, answers, or whatever else makes sense. Do not include manual labels or categorizations of the data, only the unstructured portions
- Once the script produces the output data to the `data` folder, the data should be 100% ready for ingestion by the run script
- There should be the option to filter out records in two different ways; first X records, or random sampling with a target of Y records
