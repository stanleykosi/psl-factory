# FileUpload

The one file field across the platform (D-171, concept A of the UPLOAD-concepts board): proof (signed SOW, client email, bank statement), templates, an RFP document. Drop or choose a file; it uploads at once and shows its name, size and state. Nothing else draws a file field; the assistant's attach button in the chat composer stays an icon button (a message attachment, not a form field).

- Drop zone: dashed `ink` edge, upload icon, "Drop a file here or choose a file", and what it accepts ("PDF, PNG, JPG or EML · up to 10 MB"). Turns solid blue with "Drop to upload" while a file is dragged over.
- Files sit as rows under the label, above the zone. Where more than one file is allowed, the zone shrinks to one line, "Add another file or drop it here". Where one file is allowed, the row replaces the zone until it is removed.
- File row states: uploading (clip icon, "Uploading · 1.2 of 3.4 MB", progress bar, Cancel), uploaded ("Uploaded · 420 KB", Remove), error (orange edge, the reason, Try again; Remove too where the file must go before another is added), restricted (can see that proof exists, not open it).
- Too large or the wrong type is refused in the field, as an error row with Try again, before any upload. Where the screen's service is the only rule, pass no accept list and no limit.
- Closed: a grey zone saying why ("Uploads are closed · The record is verified.").
- Phone: the zone says "Take a photo or choose a file" with a camera icon. The chooser has no `capture`, so the phone offers the camera or the files. Targets are 44px.
- Accessible: the label names the chooser and the group; hints and errors are tied with aria-describedby; Remove reads "Remove <file name>"; row text is announced as it changes.
- Proof is required where the factory needs it; the record button explains when it is missing.
