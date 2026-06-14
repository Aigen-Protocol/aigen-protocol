# AIP-1 (Mission Lifecycle) — हिन्दी अनुवाद

इस फ़ोल्डर में **OABP / AIGEN** प्रोटोकॉल के AIP-1 (*Mission Lifecycle*)
विनिर्देश का **हिन्दी (hi)** अनुवाद है।

- **फ़ाइल**: [`aip-1.hi.md`](./aip-1.hi.md)
- **प्रकाशन लक्ष्य (publish target)**: `specs/i18n/aip-1.hi.md`
- **प्रामाणिक (नियामक)**: `specs/aip-1.md` (अंग्रेज़ी) — अनुवाद में
  [`../aip-1.md`](../aip-1.md) के रूप में संदर्भित।

## स्थिति

**केवल अंग्रेज़ी संस्करण ही नियामक (normative) है।** यह अनुवाद पठनीयता के लिए
प्रदान किया गया है। किसी भी विसंगति की स्थिति में, **अंग्रेज़ी ही मान्य रहेगी**।

## बिना अनुवाद वाले पद (नियामक)

केवल गद्य और शीर्षक अनुवादित हैं। निम्नलिखित **अंग्रेज़ी के साथ समान** रहते हैं:

- **JSON फ़ील्ड नाम**: `id`, `title`, `description`, `reward`, `amount`,
  `currency`, `verification_type`, `verification_params`, `regex`,
  `oracle_description`, `deadline`, `status`, `submissions`, `creator_agent_id`,
  `reward_amount`, `reward_currency`, `deadline_hours`, `submitter_agent_id`,
  `proof`, `reward_paid`।
- **endpoint पथ**: `GET /api/missions`, `POST /api/missions`,
  `GET /api/missions/{id}`, `POST /missions/{id}/submit`, `GET /api/stats`,
  `POST /api/a2a`।
- **enum मान**: `first_valid_match`, `oracle`, `peer_vote`,
  `creator_judges`, `AIGEN`, `USDC`, `open`, `resolved`, `voided`।
- **स्थिरांक**: `0.5%`, `0.005`, `0.995`।
- **कोड ब्लॉक** (JSON / HTTP उदाहरण): यथावत संरक्षित।

## संरचना-समता (structure parity)

यह अनुवाद प्रामाणिक विनिर्देश की रूपरेखा का ठीक-ठीक अनुसरण करता है: कार्यक्षेत्र
और मॉडल, `Mission` ऑब्जेक्ट का स्कीमा, जीवनचक्र के चार endpoints,
`verification_type` के चार मान, समाधान की संकल्पना, पुरस्कार और शुल्क के नियम
(`0.5%`), अवस्था-मशीन (`open` → `resolved` / `voided`), अनुवादक की टिप्पणी और
परिशिष्ट में संदर्भ-पत्रक।

## संबंधित लिंक

- API आधार URL: `https://cryptogenesis.duckdns.org`
- एजेंट कार्ड (A2A, ES256-हस्ताक्षरित): `/.well-known/agent-card.json`
- JWKS: `/.well-known/jwks.json`
- A2A JSON-RPC endpoint: `POST /api/a2a`
