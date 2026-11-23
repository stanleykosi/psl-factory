# Speaking to Tola, Chidi and Zainab

Staff open their agent conversation and choose **Dictate message**. A device that needs a speech pack offers **Set up dictation** first. Choosing setup downloads the pack. Staff choose when to start the microphone. **Stop dictation** finishes the last words, then staff can edit the draft and choose **Send**. They can also type their entire message. A report recipient using Zainab’s payroll question menu still chooses one of the permitted questions.

The app uses the browser’s on-device speech recognition. It checks local availability and explicitly requires local processing before starting. A browser that provides only online speech recognition shows a typing prompt. The normal message form submits the reviewed text. The app has no audio upload, recording store or speech service endpoint. [Browser speech recognition specification](https://webaudio.github.io/web-speech-api/#dom-speechrecognition-processlocally)

| Browser check | Result |
| --- | --- |
| Live Railway, Tola, in the Codex in-app browser | The English speech pack installed and Tola displayed the ready-to-dictate button. During setup a draft was changed from Monday to Friday and cleared without sending. [Setup](../test-evidence/assistant-dictation-2026-11-21/railway-setup.jpg) · [Edited draft](../test-evidence/assistant-dictation-2026-11-21/railway-draft.jpg) · [Ready to speak](../test-evidence/assistant-dictation-2026-11-21/railway-ready.jpg) |
| Chrome with its own English speech engine, Chidi, local test project | With the page offline, Chrome transcribed a computer-generated voice saying “Show me the invoices due on Friday” into the unsent message. Friday was changed to Monday while still offline. After reconnecting, pressing Send queued the Monday question once. The browser received a prerecorded audio track in place of a staff microphone. [Recognized words](../test-evidence/assistant-dictation-2026-11-21/native-chrome.png) · [Edited offline](../test-evidence/assistant-dictation-2026-11-21/native-edited.png) · [After Send](../test-evidence/assistant-dictation-2026-11-21/native-sent.png) |
| Chrome with a scripted speech result, Chidi, local PostgreSQL project | The result added words to an existing draft. Send stayed disabled until recognition finished. Changing Monday to Friday made no request. Pressing Send submitted the edited question once. A separate database check found the exact Friday wording queued once. [Before sending](../test-evidence/assistant-dictation-2026-11-21/edited-draft.png) · [Queued question](../test-evidence/assistant-dictation-2026-11-21/sent-question.png) |

Four automated message-box tests passed. They cover a browser with online-only recognition, successful and unsuccessful speech-pack setup, duplicate and late words, editing a long draft, microphone permission denial and stopping on leaving the page.

All 13 PostgreSQL tests for department conversations and payroll-report questions passed. They include checks that the microphone control appears in a normal conversation and stays out of the payroll question menu and the waiting-for-answer screen.

Railway reported a successful web release and the site’s health check returned `ok`. [Railway deployment](https://railway.com/project/f957481b-c6f7-43af-bc66-449a330a9d53/service/ac6b2ef8-4bd1-4dcf-9c28-5ef5b0de0de3?id=9a6f6fb8-fe5b-483e-a8ef-ab9ca579e730)
