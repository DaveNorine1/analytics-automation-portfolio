/**
 * inquiry auto-drafter
 * watches gmail for web-form inquiries, reads each one with gemini, writes a short
 * reply in the business's voice, attaches the right files from drive, and saves it
 * as a draft in the original thread. a person reviews and hits send.
 *
 * setup: script properties GEMINI_API_KEY and DRIVE_FOLDER_ID, then run setup() once.
 */
const CONFIG = {
  businessName: 'Harbor Street Kitchen',
  signOff: 'Thanks!\nThe Harbor Street Kitchen team',
  //which emails count as new inquiries
  searchQuery: 'from:(notifications@your-form-tool.com) subject:(inquiry) -label:"1Inquiries/Drafted" -label:"1Inquiries/NeedsReview" newer_than:7d',
  labels: { drafted: '1Inquiries/Drafted', review: '1Inquiries/NeedsReview' },
  model: 'gemini-2.5-flash',
  voice: 'Warm, short, conversational. 60 to 100 words. Contractions. No corporate phrasing. Do not repeat their details back to them.',
  //attachment rules, checked top to bottom. files are exact names in the drive folder
  rules: [
    { name: 'Catering', when: i => i.type === 'catering', files: ['Catering Menu.pdf'] },
    { name: 'Large private event', when: i => i.type === 'private_event' && i.guest_count > 10,
      files: ['Main Menu.pdf', 'Events FAQ.pdf', 'Private Dining Policies.pdf', 'Catering Menu.pdf'] },
    { name: 'Small private event', when: i => i.type === 'private_event' && i.guest_count > 0,
      files: ['Main Menu.pdf', 'Events FAQ.pdf', 'Private Dining Policies.pdf'] }
  ],
  //things the draft must never do; the owner adds these by hand before sending
  guardrails: [
    'Never say a date is available or booked. Say the team will confirm availability.',
    'Never quote prices, minimums, or dollar amounts. Say minimums vary by day and time.',
    'Never promise menu substitutions or dietary accommodations. Say the team will follow up.'
  ]
};

function processInbox() {
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty('GEMINI_API_KEY');
  const folder = DriveApp.getFolderById(props.getProperty('DRIVE_FOLDER_ID'));
  const drafted = getOrCreateLabel_(CONFIG.labels.drafted);
  const review = getOrCreateLabel_(CONFIG.labels.review);

  GmailApp.search(CONFIG.searchQuery, 0, 20).forEach(thread => {
    const msg = thread.getMessages().slice(-1)[0];
    try {
      const body = msg.getPlainBody().slice(0, 8000);
      const inquiry = extractInquiry_(body, apiKey);
      const rule = pickRule_(inquiry, CONFIG.rules);
      const { files, missing } = findFiles_(folder, rule ? rule.files : []);
      const reply = writeReply_(inquiry, rule, body, apiKey);

      //the form tool sets reply-to to the customer, so a native reply threads correctly
      msg.createDraftReply(reply, { attachments: files });

      const needsReview = !rule || missing.length > 0 || !inquiry.guest_count;
      thread.addLabel(needsReview ? review : drafted);
      console.log(`${thread.getFirstMessageSubject()} -> ${rule ? rule.name : 'no rule'}${needsReview ? ' (needs review)' : ''}`);
    } catch (err) {
      thread.addLabel(review);
      console.error(`failed on "${thread.getFirstMessageSubject()}": ${err}`);
    }
  });
}

function extractInquiry_(body, apiKey) {
  const prompt = `Read this web-form inquiry and return JSON only:
{"type":"catering"|"private_event"|"other","guest_count":number|null,"first_name":string|null,"event_date":string|null,"notes":string}
"guest_count" is the number of people, even if written loosely ("about 25", "25 ppl", "two dozen").

Inquiry:
${body}`;
  const out = parseJson_(callGemini_(prompt, apiKey, true));
  if (!out.guest_count) out.guest_count = guestCountFallback_(body); //belt and suspenders
  return out;
}

function writeReply_(inquiry, rule, body, apiKey) {
  const attachLine = rule ? `We are attaching: ${rule.files.join(', ')}. Mention the attachments in one short line.` :
    'We could not tell what they need. Ask one friendly clarifying question.';
  const prompt = `You write email replies for ${CONFIG.businessName}.
Voice: ${CONFIG.voice}
Rules you must follow:
- ${CONFIG.guardrails.join('\n- ')}
${attachLine}
${inquiry.guest_count ? '' : 'The group size is missing. Ask for it.'}
Greet them by first name if known (${inquiry.first_name || 'unknown'}). Do not add a sign-off; it is added for you.

Their inquiry:
${body}

Write only the email body.`;
  return callGemini_(prompt, apiKey, false).trim() + '\n\n' + CONFIG.signOff;
}

function callGemini_(prompt, apiKey, json) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.model}:generateContent`;
  const payload = { contents: [{ parts: [{ text: prompt }] }],
    generationConfig: Object.assign({ temperature: 0.4 }, json ? { responseMimeType: 'application/json' } : {}) };
  for (let attempt = 1; attempt <= 3; attempt++) {
    const res = UrlFetchApp.fetch(url, { method: 'post', contentType: 'application/json',
      headers: { 'x-goog-api-key': apiKey }, payload: JSON.stringify(payload), muteHttpExceptions: true });
    if (res.getResponseCode() === 200) {
      return JSON.parse(res.getContentText()).candidates[0].content.parts[0].text;
    }
    if (res.getResponseCode() !== 429 && res.getResponseCode() < 500) throw new Error(res.getContentText());
    Utilities.sleep(2000 * attempt); //rate limit or server error: back off and retry
  }
  throw new Error('gemini unavailable after 3 attempts');
}

//pure helpers below are unit-tested in tests/test_helpers.js
function pickRule_(inquiry, rules) {
  return rules.find(r => r.when(inquiry)) || null;
}

function guestCountFallback_(text) {
  const m = String(text).match(/(?:guests?|people|party size|headcount|group size)[^0-9\n]{0,20}(\d{1,4})|(\d{1,4})\s*(?:guests?|people|ppl|persons)/i);
  return m ? parseInt(m[1] || m[2], 10) : null;
}

function parseJson_(text) {
  const cleaned = String(text).replace(/^```(?:json)?\s*|\s*```$/g, '').trim();
  return JSON.parse(cleaned);
}

function findFiles_(folder, names) {
  const files = [], missing = [];
  names.forEach(n => {
    const it = folder.getFilesByName(n);
    it.hasNext() ? files.push(it.next().getBlob()) : missing.push(n);
  });
  return { files, missing };
}

function getOrCreateLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}

function setup() {
  Object.values(CONFIG.labels).forEach(getOrCreateLabel_);
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('processInbox').timeBased().everyMinutes(10).create();
}

if (typeof module !== 'undefined') module.exports = { pickRule_, guestCountFallback_, parseJson_, CONFIG };
