# ChatMessage

The pieces of the assistant page.

- **Your message:** `ink` box, right-aligned.
- **Agent answer:** blue-bordered box with the avatar and name; the live checklist above it while it works; source tags under the answer.
- **Can't answer:** orange-bordered box that says why (no access, missing record) and what to do.
- **Composer:** text box with Send; focus ring on the whole box; Enter sends, Shift+Enter adds a line.
  - **Attach images (D-161):** a paperclip icon button, the same size and style as the microphone and labelled "Attach images", sits in the tool row (on phones too; the microphone does not). It opens the image chooser (`image/*`, several files; phones offer the camera as well as the photo library). Each chosen image is a small thumbnail above the text with a remove (×) in its corner, like a chip. States: uploading (the thumbnail is dimmed with the busy squares over it), ready, and refused (a signal-coloured border with the server's words word for word under it). Send stays disabled while any image is uploading or refused, and works with images and no text. On phones the remove button is a 44 px target.
  - **A sent message shows at once (D-160):** the person's message (text, @/# chips, image thumbnails) goes into the thread on the press with a muted "Sending…" under it, the box empties and Send shows the busy squares until the agent's reply arrives. A refused send takes the message out and puts everything back in the box.
- **Your message with images:** the thumbnails sit under the words inside the ink box, right-aligned; each opens the full image in a new tab.
- **Suggestions:** three to five prompts from the person's role and current work, hidden once a conversation starts on phones.
