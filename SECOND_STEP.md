# Overview

We now need to be able to run external data through this system. I've created a folder named `rawDataPreFormatted`, where I'd like to put raw data found on the web, and a python script of the same name (so it's visibly next to the existing data file), used to extract that data from that file.

# Considerations
- The script that extracts data into the needed format should output to the `data` folder, into a folder with the name of the dataset we put in there. Below that folder, there should be the extracted jsonl data file with a timestamp, and other parameters in the title, like how many records are in the file