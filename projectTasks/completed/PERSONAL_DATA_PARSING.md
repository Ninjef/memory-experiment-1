# Overview

I think it's time to start using data from my own conversations for testing. I can ALWAYS "poison" them with seeded relational undertones if I need to. And at least at that point I'll be able to understand the narrative and backstory well enough to do it in a meaningful way.

Right now I only have my google gemini chat logs. They're in a less-than-ideal HTML format (probably to protect google from folks using the data like this - but it's MY data, so not illegal or anything for me to use). So I need another data extractor like extract_locomo.py, but for gemini chat logs.

# Considerations
- I have placed my exported chat logs in rawDataPreFormatted/jeffArnoldGeminiChats/MyActivity.html
- I want there to be two python scripts
- One script takes that HTML file and turns it into a json structure with metadata about the date it was extracted from the document, who is the user (you can supply this with a command line argument), and any other overall metadata you think is important. Then it has a list of each prompt / response entry along with the datetime of the prompt / response
- That first script will need to detect when the user's message ends and the AI's response begins. There is not a perfect keyword or measurement for this, unfortunately. But if you take a look at that HTML, the general format is there's a div with "Gemini Apps" at the top to indicate a new entry, then there's a divider, and then the word "Prompted " followed immediately by the user's prompt. Then, separating the user's prompt from the AI's response is a newline with a datetime in a format like "Apr 3, 2026, 1:16:07 PM MDT" or "Mar 5, 2026, 9:43:03 AM MDT" - keep in mind that the MDT could be timezones like "PT" (only two characters)
- - Finally, just before the very end of the div is language like: Products:
 Gemini Apps
Why is this here?
 This activity was saved to your Google Account because the following settings were on: Gemini Apps Activity. You can control these settings  here. (don't quote me on that, just look for yourself)
- The second script, I do not want to implement yet, because the current task seems tricky enough on its own. But suffice it to say that after this script runs, we should output it to a new folder under rawDataPreFormatted like "jeffArnoldGeminiChats_parsedFromHTMLToJson" or something