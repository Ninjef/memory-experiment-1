# Overview

I want to make it possible to take two outputs in the output/ directory and generate a web page visualization that allows you to toggle between then two. The key here is that when you toggle between the two, I want a visibly smooth transition of the points on the interactive 3d chart to occur. So if something is at, say, x:1, y:1, z:1 and should end up at x:3, y:3, z:3, the point should visibly cross the space between at x:2, y:2, z:2.

# Considerations
- This is a post processing step that can be done apart from the main pipeline
- Consider that you may not have an ID for each of the points, so you may not know which specific point should move where. However, I'd definitely like to track the points correctly. So to do this, you may want to hash the text of each point to generate an ID or something; and deal with collisions in a hand-wavy way - don't try to reconcile collisions, just do whatever is easiest if there is one
- If easy enough, allow for doing this for more than two - the toggle should be a slider, and the text for each point on the slider should be configurable in a new metadata file in the output that will not normally be there, but can be placed there manually by a human who wants control over how this visualization looks
- If easy enough, allow for another metadata field that enables a side-by-side view of two sets of outputs tied to the same slider; for instance, set 1 on the left, with outputs A, B, and C and slider labels 1, 2, and 3, and set 2 on the right, with outputs D, E, and F and slider labels 1a, 2a, and 3a. When you move the slider, you change both graphs but see the labels each side of the slider for each respective visualization
