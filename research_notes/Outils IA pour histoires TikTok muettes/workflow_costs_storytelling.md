# Workflows, real per-video costs and wordless visual-storytelling craft for AI micro-stories (15–90 s, vertical, no dialogue) — state as of 2026-10-03

Sourcing note for the report writer: research was done on 2026-10-03. Mid-research, the session's shared web-search budget ran out, and the network proxy blocked full-text fetching for every site except cloud.google.com. So, apart from the Google Cloud Veo 3.1 guide (marked [FT] = full text read), most findings come from search-engine summaries of the linked pages (marked [SS] = search summary; the page itself was not opened). When a summary combined several pages, the figure is cited to the set of pages it came from, and attribution to a single URL is approximate. Many cost and hit-rate figures come from **vendor content marketing** (invideo, MindStudio, aiworkflows.tools, Hedra, etc.). Treat them as indicative. Items older than about 6 months (before April 2026) are flagged **[OLD]**. Dollar figures are as published. For a rough conversion, assume **$1 ≈ €0.85–0.90**. That rate is an assumption and was not checked for October 2026.

## 1. Documented step-by-step pipelines (idea → LLM beat sheet → shot list → keyframes → image-to-video → selection → upscale → sound → edit → TikTok export): concrete examples with tools, time, money and dates

### Takeaway
In 2025–2026 the documented pipeline is almost always the same chain: an LLM writes the script and shot list, then come still keyframes with a locked character reference, then image-to-video (or first/last-frame) generation, then deliberate over-generation and selection, and finally music/SFX and an edit in CapCut, Premiere or DaVinci. Documented examples range from vendor claims of about 6 hours and $15–40 for a short, to $95–197 over about 2 days, to a professional's 30-second broadcast ad at $2,000 in 2–3 days (2025). The tool landscape changed a lot in 2026. **Sora no longer exists.** Google's **Gemini Omni Flash** (I/O 2026) is now the default in the Gemini app and Flow, and it is free inside YouTube Create and Shorts Remix.

### Cited Findings

**Case studies with numbers**
- **Kalshi NBA Finals ad (June 2025) [OLD, ~16 months].** AI filmmaker PJ Accetturo made a fully AI-generated ad with Google **Veo 3** that aired during the NBA Finals. It cost **about $2,000** and took **300–400 generations to get 15 usable clips**. **One person** made it in **2–3 days**, which was reported as about a 95% cost cut versus a traditional ad. — [MarkTechPost, 14 Jun 2025](https://www.marktechpost.com/2025/06/14/ai-generated-ad-created-with-googles-veo3-airs-during-nba-finals-slashing-production-costs-by-95/); [PublicGaming](https://www.publicgaming.com/news-categories/advertising/14510-heres-the-2-000-fully-ai-generated-ad-that-aired-during-the-nba-finals); [CO/AI](https://getcoai.com/news/kalshis-nba-finals-ad-costs-just-2k-using-googles-ai-video-tool/) [SS]
- **Kalshi workflow detail [OLD].** He writes a script, then asks **Gemini** to turn it into a shot list with Veo 3 prompts. He asks for **5 prompts at a time**, because quality slipped when he asked for more. He pastes the prompts into Veo 3 and assembles the ad in **CapCut or Adobe Premiere Pro**. — [same set](https://www.publicgaming.com/news-categories/advertising/14510-heres-the-2-000-fully-ai-generated-ad-that-aired-during-the-nba-finals) [SS]
- **invideo-documented productions (2026, vendor).** A **3-minute animated episode** generated **164 Seedance 2.0 clips and used 41** (a 25% selection rate). **17 final shots were composites stitched from 2 or more generations.** A **90-second short took about 400 generations.** That works out to **about 55–270 generations per finished minute**. — [invideo FAQ: generations per usable shot](https://invideo.io/faq/how-many-ai-video-generations-do-you-need-per-usable/); [invideo FAQ: generations to budget](https://invideo.io/faq/how-many-ai-video-generations-do-you-need-to-budget-for/) [SS]
- **invideo cost and time (2026, vendor).** Documented 2026 AI short films cost **$315–750 per finished minute**. Complete shorts cost **$750–5,000** and took **2–5 days** with **teams of 1–4 people**. — [invideo: AI film production cost](https://invideo.io/blog/ai-film-production-cost/); [invideo FAQ: budgeting a short](https://invideo.io/faq/how-do-you-budget-an-ai-short-film-production/) [SS]
- **invideo agent pipeline (vendor).** A "creative producer agent" takes in the script and routes each shot to **Seedance 2.0, Veo or Kling**, using **reference sheets** to keep characters consistent. **Locking one character took about 5 generation attempts, about $9.78 per character.** — [invideo: AI filmmaking 2026 guide](https://invideo.io/blog/ai-filmmaking/) [SS]
- **invideo ads (vendor).** Teams generated **7–85 video clips per ad and used 1–13**. One production kept per-ad cost at **about $125** by **iterating still images cheaply and animating only locked frames**. — [invideo FAQ: ad asset utilization](https://invideo.io/faq/how-many-ai-generated-video-ad-assets-actually-get-used/) [SS]
- **MindStudio "short film under $200" workflow (2026, vendor blog).** The toolkit costs about **$95–197**:
  - **Claude** for scripting, $10–25
  - **Imagen 3** for concept art, $15–30
  - **Seedance 2.0** for video, $60–100
  - **Suno** for music, $10–20
  - **DaVinci Resolve or CapCut** for editing, free
  - **ElevenLabs** for optional voiceover, $0–22
  
  The blog calls it a "repeatable workflow" producing a polished short in "roughly **two days**". — [MindStudio: short film under $200 with Claude + Seedance](https://www.mindstudio.ai/blog/how-to-make-ai-short-film-under-200-claude-seedance); [MindStudio: workflow under $200](https://www.mindstudio.ai/blog/ai-short-film-production-workflow-under-200/) [SS]. Related MindStudio pages (titles only seen): [Seedance 2.0 animated short workflow and cost](https://www.mindstudio.ai/blog/ai-animated-short-film-seedance-2-0-workflow-cost), [one-person short film workflow](https://www.mindstudio.ai/blog/ai-one-person-short-film-production-workflow), [AI filmmaking cost breakdown 2026](https://www.mindstudio.ai/blog/ai-filmmaking-cost-breakdown-2026/).
- **aiworkflows.tools, "Make an AI Short Film in 6 Hours (2026)" (vendor tutorial).** The stack is ChatGPT, Midjourney, Runway or Kling, ElevenLabs, Suno and CapCut, for a 2–5 minute film. Stage times:
  - Midjourney style and storyboard: about **90 min**
  - **Animating keyframes in Kling: about 180 min**
  - ElevenLabs voiceover: about **30 min**
  - Then Suno music and a CapCut edit
  
  A companion page advertises a "9-tool workflow ($15–40)". — [aiworkflows.tools guide](https://aiworkflows.tools/blog/complete-guide-ai-short-film-production-2026); [aiworkflows.tools short-film workflow](https://aiworkflows.tools/workflows/short-film) [SS]
- **AI short drama (industrial vertical-drama context, 2026).** AI has cut per-minute drama production costs to **under $100**. A **10-episode × 5-minute drama** is viable for **under $1,500**. — [Lollipop: AI short drama production costs 2026](https://www.lollipop.im/blog/ai-production-cost/) [SS]
- **First/last-frame tutorial for 60-second shorts** (title only seen): "Make a 60-Second AI Short Film With the First-Last-Frame Workflow". — [Versely](https://www.versely.studio/blog/60-second-ai-film-first-last-frame-workflow) [SS]
- **French-language tutorial (2026)** showing how to keep the same character across all scenes with **Kling + Google Flow** (title: "Court Métrage IA 2026 Garde le Même Personnage dans Toutes les Scènes Tuto Kling & Google Flow"). — [YouTube](https://www.youtube.com/watch?v=iklXwKSINHU) [SS, title only]

**Tool landscape relevant to the pipeline (October 2026)**
- **Sora is discontinued.** OpenAI announced the shutdown on **24 March 2026**. The Sora web and mobile apps closed on **26 April 2026**, and the **API closed on 24 September 2026**. Reasons reported: Sora's very high compute cost (GPUs were redirected to more profitable text, reasoning and coding products ahead of an expected IPO) and falling usage (new downloads fell 32% from November to December 2025). The shutdown also "torpedoed a **$1 billion partnership with Disney**". — [Zilliz: Sora shutdown timeline](https://zilliz.com/ai-faq/what-is-the-sora-shutdown-timeline); [Engadget](https://engadget.com/ai/openai-is-shutting-down-its-sora-video-generation-app-211023358.html); [New Straits Times, Mar 2026](https://www.nst.com.my/amp/business/corporate/2026/03/1403261/openai-kills-sora-video-app-pivot-toward-business-tools); [AlternativeTo, Mar 2026](https://alternativeto.net/news/2026/3/openai-is-shutting-down-sora-its-ai-video-slop-app-less-than-six-months-after-launch) [SS]
- **Gemini Omni (Google I/O 2026).** Google's "any input to any output" model starts with video. **Gemini Omni Flash** rolled out to **Google AI Plus, Pro and Ultra subscribers worldwide** through the **Gemini app and Google Flow**. It is also available "**at no cost**" in **YouTube Shorts Remix and the YouTube Create app (18+)**, with APIs to follow. Google says it **improves character consistency, preserving identity and voice across scenes**, and lets you **iterate conversationally**. — [Google blog: 100 things announced at I/O 2026](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/); [Google blog: Nano Banana 2 Lite and Gemini Omni Flash](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni-flash-nano-banana-2-lite/) [SS]
- **Omni and Veo.** Demis Hassabis described Omni as combining Gemini with **Veo, Nano Banana and Genie**. Omni **replaces Veo as the default inside the Gemini app**, while Veo continues as the "high-fidelity specialist" elsewhere. — [Decrypt](https://decrypt.co/368393); [Opus Clip blog](https://www.opus.pro/blog/gemini-omni-released-multimodal-ai-video-model-explained); [Framia](https://framia.converge.ai/page/en-US/blog/google-io-2026-ai-video-gemini-omni) [SS]
- **Flow credits after I/O 2026.** Flow Omni credits are **200 on AI Plus, 1,000 on AI Pro and 10,000–25,000 on AI Ultra**. Google moved from fixed monthly prompt caps to a **compute-based usage model**, which "caused frustration among existing AI Pro subscribers". — [Opus Clip](https://www.opus.pro/blog/gemini-omni-released-multimodal-ai-video-model-explained); [Android Authority](https://www.androidauthority.com/p-3668469); [Framia](https://framia.converge.ai/page/en-US/blog/google-io-2026-ai-video-gemini-omni) [SS]
- **Model ranking, mid-July 2026** (aggregators citing the Artificial Analysis arena):

  | Model | Elo |
  |---|---|
  | Gemini Omni Flash | 1,240 |
  | Seedance 2.0 720p | 1,225 |
  | HappyHorse-1.1 | 1,149 |
  | Kling 3.0 Pro | 1,110 |

  Notes on individual models:
  - **Omni Flash** costs "a quarter of the flagship alternatives", but clips are **capped at 10 s and 720p**.
  - **Veo 3.1** is still the physics and cinematic leader, with "native 4K" and **8 s extendable** clips.
  - **Kling 3.0** offers energetic camera motion, multi-shot, and up to **15 s** (aggregators say native 4K up to 60 fps).
  - **Seedance 2.5** suits "long story beats and large reference sets".
  - **Runway Gen-4.5** is described as the strongest overall creative and editing environment.
  
  — [Hedra](https://www.hedra.com/blog/best-ai-video-models); [VideoGen](https://videogen.io/best-ai-video-models); [Tech-Insider](https://tech-insider.org/best-ai-video-generator-2026/); [mstudio](https://mstudio.ai/insights/best-ai-video-generator-2026); [Reelistic](https://reelisticapp.com/blogs/best-ai-video-generation-models-2026/) [SS]
- **Veo 3.1 when it launched (October 2025) [OLD].**
  - 720p or 1080p, **16:9 or 9:16**
  - **4, 6 or 8 s** clips, with native synchronized audio and SynthID watermarking
  - **First & Last Frame** transitions, **Ingredients to Video** (reference images for consistent characters, objects and style) and **timestamp prompting** for multi-shot sequences in one generation
  - Google recommends making the reference and keyframe images with **Gemini 2.5 Flash Image (Nano Banana)**
  
  — [Google Cloud blog, 16 Oct 2025](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) [FT]
- **Kling community notes (2026).** The negative-prompt feature was extended to **image-to-video in Kling 3.0**. — [VEED Kling 3.0 guide](https://www.veed.io/learn/kling-3-0-prompts); [Atlabs](https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation) [SS]. Reddit-based roundups say **Kling v3.0's credit cost (90–120 credits per clip) caused a backlash**, pushing many r/aivideo users back to **v2.6 for volume work**, and that r/aivideo rates **Seedance 2.0** among the most advanced models. — [NemoVideo: Reddit recommendations](https://www.nemovideo.com/blog/ai-video-generators-reddit-recommendations) [SS]

### Inferences
- A beginner-sized version of the documented pipeline for a 15–90 s wordless piece:
  1. Turn a feeling into a one-line metaphor, using Claude, ChatGPT or Gemini.
  2. Write a 3–7 beat sheet.
  3. Write a shot list of 5–15 shots, each 2–5 s.
  4. Write a "style bible" text block and make a character sheet in an image model.
  5. Make one still keyframe per shot.
  6. Run image-to-video, budgeting 3–5 attempts per shot.
  7. Select and trim the best takes.
  8. Add music, ambience and SFX.
  9. Edit in CapCut or DaVinci and export 9:16.
  
  The Kalshi, MindStudio and aiworkflows examples all follow this order. The main variation is whether you anchor shots with stills; the vendor data favours stills.
- Any 2025 tutorial built around Sora (or the Sora prompting guide) is now obsolete for practical use. In October 2026 the beginner's realistic options are Google (Omni Flash or Veo 3.1 via Gemini, Flow or YouTube Create), Kling (3.0, or 2.6 for volume), Seedance, Runway, Hailuo/MiniMax and similar.
- The Kalshi ratio (about 20–27 generations per usable clip, text-to-video, comedic multi-character scenes with dialogue, mid-2025) is a worst-case reference. The 2026 vendor ratios (about 3–5 per usable shot) assume image-anchored shots and reference sheets. A wordless, single-character piece with slow, simple actions should land nearer the low end.
- For wordless stories with native-audio models (Veo, Omni, Kling 3.0), the prompt has to direct the audio explicitly. Ask for ambience, SFX or music only, or generate without audio and add sound in the edit, so the model doesn't invent speech. This is inferred from the Veo guide's emphasis on explicit audio cues; no source tested "no dialogue" prompts.
- Omni Flash's 720p cap suggests an upscaling pass, or picking a higher-resolution model for hero shots, if 1080×1920 sharpness matters. Veo 3.1 or Kling 3.0 at 1080p or 4K may make upscaling unnecessary for TikTok. This is an inference; no source on TikTok's playback resolution was retrieved.

### Gaps
- I found no independent (non-vendor) 2026 creator breakdown with a full time and money log for a 15–90 s wordless emotional piece. Reddit, X and YouTube could not be opened, and the search budget ran out.
- The credit cost per generation in Flow under the new compute-based model (Omni Flash and Veo 3.1, October 2026) and Flow plan prices in EUR were not verified. Use the pricing researcher's tables.
- The exact date of Google I/O 2026 was not verified.
- Topaz Video AI (2026 price, typical use for AI clips) and built-in upscalers were not researched successfully. Frame interpolation needs are unknown.
- Limitations of free Omni Flash in YouTube Create and Shorts Remix (watermarks, export rights, quotas, whether clips can be exported for TikTok) were not verified.

## 2. Realistic "hit rate", cost per finished minute, and what each budget tier (€0 / ~€10–30 / ~€50–100 / €200+ per month) can realistically produce

### Takeaway
Plan for about **3–5 generations per usable shot** with image-anchored workflows (some shots take 8 or more), and a **25–40% clip keep rate**. Pure text-to-video can be far worse: the 2025 Kalshi ad needed about 20–27 per usable clip. Published cost per finished minute ranges from **under $100** (industrial short-drama pipelines) to **$315–750** (vendor-documented cinematic shorts). For a hobbyist, the real limits are monthly generation allowance and personal time. A 30–45 s wordless piece needs roughly **30–50 video generations plus 40–70 image generations**, so output per tier is approximately the monthly allowance divided by that.

### Cited Findings
- About **3 generations per usable shot** is the "working average". A realistic hit rate on a given shot is **1 usable clip in 3–5 attempts**; "some shots land on the first try, others take **8+** tries". About **25%** of generated clips make the final cut. For planning, multiply target shot count by **about 4** and assume **about 40% of finals will be stitched composites** ("Frankenstein shots" built from the best seconds of several takes). — [invideo FAQ: generations per usable shot](https://invideo.io/faq/how-many-ai-video-generations-do-you-need-per-usable/); [invideo: AI shot generation](https://invideo.io/blog/ai-shot-generation/); [invideo FAQ: usability rate](https://invideo.io/faq/what-percentage-of-ai-generated-video-clips-are-actually-2/) [SS, vendor]
- Expect to use **25–40% of generated video clips and 15–30% of generated images** in the final cut. The planning rule is to generate **about 3–5 clips for every 1 you need**. — [invideo FAQ: ad asset utilization](https://invideo.io/faq/how-many-ai-generated-video-ad-assets-actually-get-used/) [SS, vendor]
- **55–270 generations per finished minute.** The low end comes from 164 clips for a 3-minute episode (about 55 per minute); the high end from about 400 for a 90-second short (about 267 per minute). — [invideo FAQ: generations to budget](https://invideo.io/faq/how-many-ai-video-generations-do-you-need-to-budget-for/) [SS, vendor]
- **Kalshi [OLD, June 2025]: 300–400 generations for 15 usable clips** (about 4–5% keep, about 20–27 generations per clip), Veo 3 text-to-video. — [MarkTechPost](https://www.marktechpost.com/2025/06/14/ai-generated-ad-created-with-googles-veo3-airs-during-nba-finals-slashing-production-costs-by-95/) [SS]
- Locking a character takes **about 5 attempts, about $9.78 per character**. Generating **4 options per asset, picking one and locking it** "prevents consistency re-rolls later". — [invideo: AI filmmaking](https://invideo.io/blog/ai-filmmaking/); [invideo FAQ](https://invideo.io/faq/how-many-ai-video-generations-do-you-need-per-usable/) [SS, vendor]
- **Cost per finished minute (these conflict):**
  - **$315–750 per minute** for documented AI short films; [invideo](https://invideo.io/blog/ai-film-production-cost/) [SS, vendor]
  - **under $100 per minute** for AI short drama; [Lollipop](https://www.lollipop.im/blog/ai-production-cost/) [SS]
  - **$95–197 toolkit** for a short film; [MindStudio](https://www.mindstudio.ai/blog/how-to-make-ai-short-film-under-200-claude-seedance) [SS]
  - **"$15–40" 9-tool workflow**; [aiworkflows.tools](https://aiworkflows.tools/workflows/short-film) [SS]
  - **$2,000 for a 30-s-class broadcast ad**; [Kalshi, OLD](https://www.marktechpost.com/2025/06/14/ai-generated-ad-created-with-googles-veo3-airs-during-nba-finals-slashing-production-costs-by-95/) [SS]
  
  The spread reflects different quality bars, lengths, and whether labor or subscriptions are counted.
- A 2026 developer post frames the economics as "**the expensive part is the failed shot, not the generate button**" (title only seen). — [DEV Community](https://dev.to/ugliai/ai-video-in-2026-the-expensive-part-is-the-failed-shot-not-the-generate-button-215l) [SS]
- **Allowance data points for tiers:**
  - Flow Omni credits are **200 (AI Plus), 1,000 (AI Pro) and 10,000–25,000 (AI Ultra)** per month, under compute-based usage; [Opus Clip](https://www.opus.pro/blog/gemini-omni-released-multimodal-ai-video-model-explained) [SS]
  - **Omni Flash is free (18+) in YouTube Create and Shorts Remix**; [Google blog](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/) [SS]
  - Omni Flash costs about **a quarter of flagship models**, with a 10 s / 720p cap; [Hedra](https://www.hedra.com/blog/best-ai-video-models) [SS]
  - **Kling 3.0 costs 90–120 credits per clip** (r/aivideo backlash), and users fall back to v2.6 for volume; [NemoVideo](https://www.nemovideo.com/blog/ai-video-generators-reddit-recommendations) [SS]
- **Cost-control tactic** documented by the vendor: iterate stills first and animate only locked frames, which kept an ad at about $125. — [invideo](https://invideo.io/faq/how-many-ai-generated-video-ad-assets-actually-get-used/) [SS]

### Inferences
- **Generation budget for one wordless micro-story** (derived from the ratios above). Take 8–10 shots of 3–5 s for a 30–45 s piece:
  - Video: 3–5 attempts per shot gives **about 30–50 video generations**.
  - Keyframes: 15–30% image keep gives **about 35–65 image generations**, plus about 5 to lock the character.
  - A 60–90 s piece is roughly double: **about 60–100+ video generations**.
  - A 15 s piece with 4–5 shots needs **about 15–25 video generations**.
- **Indicative tiers.** These are estimates; plug in the pricing researcher's per-generation costs to firm them up.
  - **€0 (free tiers only):** learning mode. Combine free Omni Flash (YouTube Create, 10 s / 720p clips), free daily or monthly credits on other platforms (amounts unverified), free image tools and free CapCut or DaVinci. Realistically **1–2 short pieces (15–30 s) per month**, with constraints on resolution, watermarks and queues. Good for practising storytelling, not for a regular posting schedule.
  - **About €10–30 per month (one entry plan, e.g. Google AI Plus or one video-tool starter plan):** about **1–4 pieces per month**, closer to 1–2 at 45–60 s and 3–4 at 15–30 s, if you stay disciplined (stills first, short shots, few re-rolls). AI Plus's 200 Flow credits are a fifth of AI Pro's, so it is probably tight for more than one or two pieces. Credit costs per generation are unverified.
  - **About €50–100 per month (e.g. Google AI Pro, or a mid Kling/Runway plan, optionally plus a music tool):** about **4–10 pieces of 30–60 s per month**, i.e. one or two a week. At this tier time becomes the main limit.
  - **"Pro" €200+ per month (e.g. Google AI Ultra at 10,000–25,000 credits, or several plans):** generation stops being the bottleneck. **20+ pieces per month** is technically possible, but each still needs hours of writing, selecting and editing.
- **Hobbyist cost per minute.** In subscription terms the cost per finished minute is far below vendor figures. For example, €25 per month for two 45 s pieces is about €17 per finished minute. Failed generations still consume about 60–75% of the credits.
- **Shot design drives the hit rate** (inferred from Kling's artifact list and the micro-expression advice). Good hit rates: slow push-ins on a face, one figure walking, light or weather changes, symbolic objects (a cup going cold, a plant wilting), silhouettes, static or slow cameras. Poor hit rates: hands handling objects, two characters touching or hugging, fast action, crowds, readable text and mirrors. A beginner can **design the story around easy shots** and cut the cost per video by 2–3 times.

### Gaps
- I found no independent survey of hit rates. The detailed ratios come mostly from one vendor (invideo), which has an interest in presenting over-generation as normal.
- Free-tier quotas in October 2026 (Kling daily credits, Hailuo, Vidu, Pika, Meta and similar) and whether failed or blocked generations are refunded on each platform were not verified.
- Credit cost per Omni Flash or Veo generation in Flow after the move to compute-based usage was not verified, so the tier outputs above are reasoned estimates, not measured figures.
- The EUR prices of the plans that define each tier are left to the pricing researcher.

## 3. Prompting techniques for wordless emotional storytelling with current video models (micro-expressions, body language, gaze, pacing, camera, light/colour, structured/JSON prompts, negative prompts, artifact avoidance, style consistency, first/last-frame chaining, official guides)

### Takeaway
Official and practitioner guides agree. Write like a cinematographer: **shot size and camera, subject, one clear action, setting, then style, light and mood, plus audio cues**. Convey emotion through **visible physical evidence**: gaze, brow, mouth, shoulders, hands, ideally **one restrained change per shot**, not emotion adjectives. Lock the look with **reference images and first/last frames**. Use negative prompts in Kling. In Veo, describe what should be absent in positive terms. Sora's official guide is moot now that Sora has shut down.

### Cited Findings

**Google, official Veo 3.1 guide (16 Oct 2025) [FT] [OLD, ~11.5 months; still Google's main public Veo guide found]** — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- **Formula:** [Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]. Example: "Medium shot, a tired corporate worker, rubbing his temples in exhaustion, in front of a bulky 1980s computer in a cluttered office late at night. … harsh fluorescent overhead lights and the green glow of the monochrome monitor. Retro aesthetic, shot as if on 1980s color film, slightly grainy."
- **Camera vocabulary:**
  - Movement: dolly, tracking, crane, aerial, slow pan, POV, 180-degree arc
  - Composition: wide, close-up, extreme close-up, low angle, two-shot, medium, reverse shot, high-angle crane
  - Lens and focus: shallow depth of field, wide-angle, soft focus, macro, deep focus
- **Emotion:** use cinematic language and mood adjectives ("melancholic", "awe-inspiring", "wonder and reverence"), and tie the expression to its context, e.g. "her expression filled with awe as she gazes upon ancient, moss-covered ruins".
- **Audio:** dialogue goes in quotes. Use labelled **"SFX:"** cues (e.g. "SFX: thunder cracks in the distance") and **"Ambient noise:"** lines. Music can be cued, e.g. "SFX: A swelling, gentle orchestral score begins to play".
- **Negative prompting:** describe what to exclude in positive terms. Write "a desolate landscape with no buildings or roads" rather than "no man-made structures".
- **First & Last Frame:** generate two keyframes (e.g. with Gemini 2.5 Flash Image), then prompt the camera transition between them.
- **Ingredients to Video:** reuse the same character and setting reference images in every shot for consistency.
- **Timestamp prompting:** one 8-s generation scripted as four 2-s beats with shot sizes, an "Emotion:" line and SFX/music cues. The example arc is a medium shot from behind pushing aside a vine → reverse close-up of the face "filled with awe" → tracking shot touching carvings ("Emotion: Wonder and reverence") → wide high-angle crane shot of the lone explorer "standing small" as an orchestral score swells.
- **Principles:** be specific, layer details, use references, describe audio, generate references with Gemini's image model.

**Kling 3.0 (2026 guides; Kling's own blog could not be opened)**
- **Structure:** 5 parts — subject details, motion, camera work, environment, and style/lighting. — [VEED](https://www.veed.io/learn/kling-3-0-prompts); [Atlabs](https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation); [fal.ai](https://blog.fal.ai/kling-3-0-prompting-guide/) [SS]
- **Close-ups:** close-ups carry facial emotion, and "because the camera is close to the subject, **lighting stability becomes more important**". For character shots, specify character, emotion, camera distance and lighting. — [Magic Hour: Kling 3.0 reference guide](https://magichour.ai/blog/kling-30-reference-guide); [Imagine.art](https://www.imagine.art/blogs/kling-3-0-prompt-guide) [SS]
- **Negative prompts** reduce motion blur, morphing, distortion and physics errors. Example: "Negative: motion blur, face distortion, warping, morphing, inconsistent physics, floating objects, unnatural movements, extra limbs, background shifting". Other common terms: "deformed hands, extra fingers", "flicker", "warped text". Since Kling 3.0, negative prompts also work in **image-to-video**. — [Kling blog: negative prompts](https://kling.ai/blog/kling-ai-negative-prompts-fix-video-distortion); [VEED](https://www.veed.io/learn/kling-3-0-prompts) [SS]
- Kling 3.0 guides also cover **character references, camera moves and native audio** (title). — [Magic Hour: how to use Kling 3.0](https://magichour.ai/blog/how-to-use-kling-30) [SS]

**Micro-expressions, gaze and body language (2026 practitioner guides for MiniMax H3, Seedance 2.5, Hailuo, Kling)**
- "**Name the emotion, the visible facial evidence, the trigger, and the moment it settles.** Use **one restrained change** — such as eyes softening and a jaw releasing — rather than a stack of dramatic emotion words." — [Seedance.tv: MiniMax H3 microexpression prompts](https://www.seedance.tv/blog/minimax-h3-microexpression-prompts) [SS]
- **Replace abstract words** ("happy", "sad") with visible cues. Happy: "eyes somewhat narrowed with real warmth, corners crinkling naturally". Sad: "lips pressed together, gaze downward, faint furrow between eyebrows". **Highlight only one or two facial features**, because "too much detail bewilders the AI and produces stilted outcomes". — [Viddo: micro-expression prompts](https://viddo.ai/tutorial/ai-video-micro-expression-prompts); [Hailuo: realistic micro-expressions](https://hailuoai.video/pages/knowledge/micro-expressions-realistic-human-ai-video) [SS]
- **Body:** "shoulders slump in fatigue or square in confidence, hands fidget in nervousness or casually rest at someone's side — these little details sell the emotion just as much as facial expressions." — [Kling blog: 5 advanced prompting techniques](https://kling.ai/blog/ai-video-prompts-advanced-techniques-realistic) [SS]
- **Image-to-video:** the face and composition are already set by the image, so "spend prompt space on **motion, expression timing, gaze and what must remain unchanged**", not on redesigning the person. — [GPTProto: Seedance 2.5 emotional facial-expression guide](https://gptproto.com/blog/seedance-2-5-emotional-facial-expression-prompt-guide); [Seedance.tv](https://www.seedance.tv/blog/minimax-h3-microexpression-prompts) [SS]
- Runway publishes an AI video prompting guide (could not be opened). — [Runway resources](https://runway.com/resources/ai-video-prompting-guide) [SS, title only]

**Workflow-level prompting evidence**
- Asking an LLM (Gemini) for **5 shot prompts at a time** gave better quality than larger batches. — [PublicGaming (Kalshi), OLD](https://www.publicgaming.com/news-categories/advertising/14510-heres-the-2-000-fully-ai-generated-ad-that-aired-during-the-nba-finals) [SS]
- Gemini Omni Flash supports **conversational iteration** and keeps **identity and voice consistent across scenes**. — [Google blog](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/) [SS]
- Vendor practice is to generate **4 options per asset, pick one, and lock it**, plus **reference sheets** for every character. — [invideo](https://invideo.io/blog/ai-filmmaking/) [SS]
- **Sora 2 prompting guide:** the product and API are discontinued (app closed 26 April 2026, API 24 September 2026), so it is no longer a practical resource. — [Zilliz](https://zilliz.com/ai-faq/what-is-the-sora-shutdown-timeline) [SS]

### Inferences
- **Template for a wordless emotional shot,** combining Veo's formula with the micro-expression advice: *[shot size + lens + camera move] + [character from reference] + [one physical action] + [one micro-expression change with its trigger and its settle] + [setting] + [light/colour/grain style-bible block] + [Audio: ambience / SFX / music only — no dialogue]*. For image-to-video, drop the appearance description and spend the words on motion, timing, gaze and "keep X unchanged".
- **Use emotional camera grammar consistently.** The Veo vocabulary covers what's needed:
  - Extreme close-up or close-up for inner feeling
  - Slow dolly-in for a realization
  - Wide or high-angle "standing small" for loneliness or awe (the Veo example uses exactly this)
  - Low angle for empowerment
  - Static locked-off frame for numbness or stillness
  - Shallow depth of field to isolate the character
- **Style bible.** Keep one fixed text block (medium/style, palette, light quality, lens, grain, aspect ratio 9:16) and paste it unchanged into every prompt. Add one approved character sheet and one approved setting image, used as references in every shot. This puts into practice Veo's "Ingredients", Omni's consistency claims and the vendor "lock" practice.
- **Continuity by chaining.** Use the last frame of shot N, or a close variant, as the first frame of shot N+1 through first/last-frame tools. Make the final frame match the first frame for a seamless TikTok loop. This follows from the documented first/last-frame feature; no source measured its effect on hit rate.
- **One action and one camera move per generation.** Very short shots (2–5 s) suit TikTok pacing and reduce morphing risk. This is consistent with the "one restrained change" advice and Kling's artifact list.

### Gaps
- **JSON or structured prompts for Veo:** no source was retrieved before the search budget ran out. Whether JSON beats well-ordered natural language is unverified. Google's official guide (above) uses natural language, labelled audio lines and timestamp blocks, not JSON.
- No official Gemini Omni prompting guide was found or verified.
- Runway's official guide and Kling's official blog posts could not be read in full; they are summarized only through search snippets.
- No source quantified how much negative prompts or first/last-frame chaining improve the keep rate.

## 4. Visual storytelling principles for wordless micro-stories (silent film, Pixar shorts, show-don't-tell, metaphor, compressed 3-act structure, setup/payoff, twists, loops, symbolism, colour scripts) and how to turn one's own feelings into such stories

### Takeaway
Without dialogue, the story has to travel through **body language, expressions, gestures, the environment, composition, lighting and sound**. Classic models that compress well into 15–60 s are the silent-film tradition, wordless Pixar shorts like *Tin Toy*, and single-location, single-character shorts like *The Black Hole*. Google's own 8-second timestamp example shows that a complete beat arc (setup → reveal → emotional reaction → wide "payoff" image with a musical swell) fits inside one clip. Few verified sources on canonical craft could be retrieved this session (see Gaps).

### Cited Findings
- StudioBinder on writing a short **without dialogue**:
  - The silent era is recommended research; also study "neo-silent" director **Kim Ki-duk** and dialogue-free animation like **Shaun the Sheep Movie**.
  - Without dialogue, "the narrative unfold[s] through **body language, expressions, gestures, and the visual environment itself**", with carefully crafted **composition and lighting**.
  - Pixar's **Tin Toy** is cited as a model wordless short (animation and live action differ in execution).
  - **The Black Hole** is cited as a complete story with **one location, one character, no spoken words**, in which "the character's intentions are communicated purely through visual language".
  
  — [StudioBinder: short film script without dialogue](https://www.studiobinder.com/blog/how-to-write-a-short-film-script-without-dialogue/) [SS]; see also [FilmLifestyle: writing a short film script without dialogue](https://filmlifestyle.com/how-to-write-a-short-film-script-without-dialogue/) [SS, title only]
- **Compressed structure inside a single AI generation:** Google's 8-s timestamp prompt runs four 2-s beats (approach → reverse shot of the face "filled with awe" → touching the carvings, "Emotion: Wonder and reverence" → wide crane shot of the explorer "standing small" with a swelling orchestral score). Each beat uses a different shot size, and **sound and music mark the emotional peak**. — [Google Cloud Veo 3.1 guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) [FT]
- **The emotional micro-arc inside one shot:** "name the emotion, the visible facial evidence, **the trigger, and the moment it settles**". — [Seedance.tv](https://www.seedance.tv/blog/minimax-h3-microexpression-prompts) [SS]
- **Mood is a formal prompt component** ("Style & Ambiance": aesthetic, mood, lighting), and colour and light are given explicitly, e.g. "green glow of the monochrome monitor", "1980s color film, slightly grainy". — [Google Cloud Veo 3.1 guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) [FT]

### Inferences
These are derived from the findings above plus reasoning, for the writer to frame as method rather than as cited fact.
- **Micro-story skeletons by length:**
  - **15 s:** 3 beats — a situation that shows the feeling, a turn, a final image that lands; about 4–5 shots.
  - **30–45 s:** 4–5 beats — hook image (0–2 s), want or wound, obstacle or turn, emotional peak with a sound or music swell, payoff image that echoes the opening; about 8–10 shots.
  - **60–90 s:** 5–7 beats, about 12–20 shots.
  
  Each beat is **one visible action plus one visible emotional change**, which matches the one-change-per-shot prompting rule.
- **Setup and payoff without words:** plant an object in shot 1 (a key, a coat, an empty chair) and transform it in the last shot. A **loop ending**, where the last frame matches the first, is technically easy with first/last-frame tools and suits TikTok replays.
- **Turning one's own feelings into stories:**
  1. Name the feeling.
  2. Externalize it as a **metaphor character, object, weather or space** (e.g. anxiety as a growing paper storm, grief as a coat that no longer fits).
  3. Give it a recurring **avatar** with one locked reference sheet.
  
  A recurring stylized avatar also cuts cost, because the character lock (about 5 attempts) is paid once. It improves consistency across episodes and avoids realistic-person, deepfake and labelling problems.
- **Sound replaces dialogue.** Because sound and music mark the peaks in Google's own example, the wordless creator should plan the sound beat by beat: silence, breath, room tone, a single sound motif, then music on the turn.

### Gaps
- Canonical craft sources could **not be verified this session** (search budget exhausted, sites blocked). The writer may know them as general film literacy but should cite carefully: Emma Coats' "Pixar's 22 rules of storytelling" (2011), Kenn Adams' "Story Spine" (Once upon a time… Every day… Until one day… Because of that… Until finally… Ever since then…, taught in Khan Academy's *Pixar in a Box*), the Kuleshov effect, Pixar colour scripts, T.S. Eliot's "objective correlative", and TikTok hook/loop retention practice.
- No sourced examples were found of AI creators building a recurring emotional avatar or metaphor-character series, and no data on how wordless AI micro-stories perform on TikTok.

## 5. Time investment, learning curve, and the best free learning resources (French and English)

### Takeaway
Published claims run from a "first AI video in 60 minutes" (15–60 s) to about 6 hours for a 2–5 minute short, about 2 days for a polished short, and 2–3 days for a professional 30-second ad. For a beginner's first 30–60 s wordless piece, an evening to a weekend is realistic. French-language YouTube has active 2026 tutorials on Kling and Google Flow (character consistency, short films). The best free official English resource retrieved is Google's Veo prompting guide.

### Cited Findings
- **Beginner timing claims:**
  - "Make your **first AI video in 60 minutes**", aiming for "a clean **15 to 60-second** video", starting with "choosing constraints (5 minutes)"; [Neolemon beginner's guide 2026](https://www.neolemon.com/blog/beginners-guide-to-ai-video-creation-from-zero-to-hero/) [SS]
  - Keeping the first project to **30–60 seconds** "is where you learn fastest"; "concept to a fully realized short film in a mere 2 hours"; "most learners complete their first cinematic short within a single weekend after starting a course". These quotes are attributed to the set: [Neolemon](https://www.neolemon.com/blog/beginners-guide-to-ai-video-creation-from-zero-to-hero/), [Scriptly](https://scriptlyai.app/blog/ai-filmmaking-for-beginners), [Class Central](https://www.classcentral.com/report/best-ai-video-generation-courses/) [SS; exact attribution uncertain; marketing-flavoured]
  - AI-assisted editing has a learning curve of "**hours to days**", versus weeks or months for traditional editing; [VFXAI](https://www.vfxai.com/blog/how-to-edit-video-first-time-ai) [SS]
- **Workflow timings:**
  - Midjourney storyboard about **90 min**, Kling animation about **180 min**, voiceover about **30 min**, for about **6 h** total; [aiworkflows.tools](https://aiworkflows.tools/blog/complete-guide-ai-short-film-production-2026) [SS]
  - About **2 days** for a polished short; [MindStudio](https://www.mindstudio.ai/blog/how-to-make-ai-short-film-under-200-claude-seedance) [SS]
  - **2–5 days, 1–4 people**; [invideo](https://invideo.io/blog/ai-film-production-cost/) [SS]
  - **2–3 days**, one professional, for a 30-s-class ad; [Kalshi, OLD](https://www.marktechpost.com/2025/06/14/ai-generated-ad-created-with-googles-veo3-airs-during-nba-finals-slashing-production-costs-by-95/) [SS]
- **Free English resources found:**
  - **Google Cloud's "Ultimate prompting guide for Veo 3.1"** (formula, camera vocabulary, audio, first/last frame, ingredients, timestamp prompting); [Google Cloud](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) [FT]
  - **Runway's AI video prompting guide**; [Runway](https://runway.com/resources/ai-video-prompting-guide) [SS]
  - **Kling's blog** (negative prompts; advanced realism techniques); [Kling](https://kling.ai/blog/kling-ai-negative-prompts-fix-video-distortion) [SS]
  - **Kling 3.0 prompting guides**; [fal.ai](https://blog.fal.ai/kling-3-0-prompting-guide/), [VEED](https://www.veed.io/learn/kling-3-0-prompts), [Magic Hour](https://magichour.ai/blog/kling-30-reference-guide) [SS]
  - **Class Central's "7 Best AI Video Generation Courses (Free & Paid)"**; [Class Central](https://www.classcentral.com/report/best-ai-video-generation-courses/) [SS]
  - **StudioBinder** on wordless scripts; [StudioBinder](https://www.studiobinder.com/blog/how-to-write-a-short-film-script-without-dialogue/) [SS]
- **French-language resources found (2026):**
  - YouTube, "Court Métrage IA 2026 Garde le Même Personnage dans Toutes les Scènes Tuto Kling & Google Flow" (character consistency across scenes); [YouTube](https://www.youtube.com/watch?v=iklXwKSINHU)
  - "Kling 3.0 : Créez un film de 2 minutes en un seul Prompt."; [YouTube](https://www.youtube.com/watch?v=MFUV7SmTEos)
  - "Intro Formation Kling AI : l'IA Générative Vidéo !"; [YouTube](https://www.youtube.com/watch?v=O4alvZL9O48)
  - "Tuto Formation Kling AI : l'IA Générative Vidéo !"; [YouTube](https://www.youtube.com/watch?v=S1Nlc0lHwt8)
  - "Exclu ! Kling Pousse La Vidéo IA à Un Niveau Jamais Vu"; [YouTube](https://www.youtube.com/watch?v=nfBugRQG-64)
  - The French YouTube channel **ExplorIA** is cited for in-depth Kling coverage [SS, via the same search]
  - Written French guides: [Plateya, "Kling AI : Le Guide Complet 2026"](https://www.plateya.fr/blog/detail/kling-ai-le-guide-complet-2026-mise-a-jour-v20-tuto-expert); [eesel, "Comment utiliser Kling AI : Guide du débutant pour 2026"](https://www.eesel.ai/blog/kling-ai) (sign up on klingai.com, choose "Professional" mode for aspect-ratio and duration options); [Intelligence-artificielle.com on combining Kling, Veo, Seedance and GPT Image](https://intelligence-artificielle.com/anyvids-combinaison-kling-veo-seedance-gpt-image/) [SS]
  
  The YouTube items are titles only; channel names could not be read because YouTube was blocked.

### Inferences
- **Realistic beginner time budget** (reconciling the claims above):
  - First wordless 30–60 s piece: about **4–12 hours** across a weekend, including learning the interfaces, building the character sheet and making the sound edit.
  - After 5–10 pieces, plausibly **2–5 hours per 30–45 s piece**.
  
  The "60 minutes" claims fit a first rough 15–30 s test, not a crafted emotional story.
- **Suggested learning order:**
  1. One evening on Google's Veo guide and one French Kling tutorial.
  2. Make a 15 s single-shot "feeling" exercise.
  3. Make a 30 s, 3-beat piece with one recurring avatar.
  4. Then try first/last-frame loops and the sound design.

### Gaps
- Curious Refuge's free content, Runway Academy, Google Flow's official tutorials or help centre, and Kling's official tutorials could not be verified this session. They should be presented only as "to check".
- The French channels behind the listed videos, beyond the ExplorIA mention, and their subscriber counts and quality could not be confirmed.
- No survey or independent data was found on how long beginners actually take.

## 6. Common beginner mistakes and pitfalls, plus legal and ethical notes (France/EU copyright, deepfakes, imitating IP, platform terms)

### Takeaway
The main money-wasters are text-to-video re-rolling, animating images before they are locked, unplanned multi-shot scripts, chasing premium models, and stacking or prepaying subscriptions on platforms whose pricing changes, or which can disappear like Sora. The main legal points:
- **EU AI Act Article 50** labelling of AI-generated or manipulated content applies from **2 August 2026** for professional use.
- **TikTok requires an AIGC label** on realistic AI-generated people or scenes.
- **French copyright** protects only works bearing free, creative human choices, so creators should keep a log of their process.

Avoid real people's likenesses and protected characters or styles.

### Cited Findings

**Credits, subscriptions and platform risk**
- Failed shots are the main cost driver ("the expensive part is the failed shot, not the generate button"). — [DEV Community](https://dev.to/ugliai/ai-video-in-2026-the-expensive-part-is-the-failed-shot-not-the-generate-button-215l) [SS, title]
- Over-generation should be planned as a line item (about 4× the target shot count), and stills should be iterated before animating. — [invideo FAQ](https://invideo.io/faq/how-many-ai-video-generations-do-you-need-per-usable/); [invideo ad assets](https://invideo.io/faq/how-many-ai-generated-video-ad-assets-actually-get-used/) [SS]
- **Pricing changes mid-subscription:**
  - Kling 3.0 at 90–120 credits per clip caused a user backlash; [NemoVideo](https://www.nemovideo.com/blog/ai-video-generators-reddit-recommendations) [SS]
  - Google's move to compute-based Flow usage frustrated AI Pro subscribers; [Opus Clip](https://www.opus.pro/blog/gemini-omni-released-multimodal-ai-video-model-explained) [SS]
- **Platforms can vanish.** The Sora app shut down **less than six months after launch** (announced 24 March 2026; app closed 26 April 2026; API closed 24 September 2026). — [AlternativeTo](https://alternativeto.net/news/2026/3/openai-is-shutting-down-sora-its-ai-video-slop-app-less-than-six-months-after-launch); [Zilliz](https://zilliz.com/ai-faq/what-is-the-sora-shutdown-timeline) [SS]

**Consistency and artifacts**
- Characters must be locked with reference sheets, about 5 attempts each; consistency re-rolls happen when assets are not locked early. — [invideo](https://invideo.io/blog/ai-filmmaking/) [SS]
- Typical artifacts to plan around: face distortion, warping and morphing, inconsistent physics, floating objects, extra limbs, deformed hands and extra fingers, background shifting, flicker, warped text. — [Kling blog](https://kling.ai/blog/kling-ai-negative-prompts-fix-video-distortion) [SS]
- Stacking many emotion words or facial details produces "stilted" results. — [Viddo](https://viddo.ai/tutorial/ai-video-micro-expression-prompts) [SS]

**EU: AI Act Article 50 transparency (in force for deployers from 2 August 2026)**
- From **2 August 2026**, anyone using AI to generate images, audio or video **for professional purposes** may need to label it as AI-generated or manipulated. — [Lewis Silkin, 31 Jul 2026](https://www.lewissilkin.com/insights/2026/07/31/the-new-ai-labelling-rules-for-deployers-in-the-advertising-supply-chain) [SS]
- Article 50(4) obliges **deployers** to disclose **deepfakes**. Under Article 3(60), a deepfake is AI-generated or manipulated image, audio or video content that **resembles existing persons, objects, places, entities or events** and **would falsely appear authentic**. — [SRD Rechtsanwälte](https://www.srd-rechtsanwaelte.de/en/blog/deepfake-labelling-under-the-ai-act-what-the-new-eu-guidance-clarifies); [Heuking, 21 Jul 2026](https://www.heuking.de/en/news-events/newsletter-articles/detail/the-european-commission-specifies-labelling-requirements-for-ai-generated-content-and-deepfakes.html) [SS]
- **Format of the label** under the Commission's July 2026 guidance: "clear and distinguishable", understandable including for children, **perceptible without technical aids (visible or audible)**, so **a purely machine-readable marker is not enough**, and shown **at the latest upon first exposure**. — [SRD Rechtsanwälte](https://www.srd-rechtsanwaelte.de/en/blog/labelling-requirements-ai-act-deepfakes); [CSA research note, 29 Jul 2026](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/07/CSA_research_note_eu_ai_act_article_50_transparency_20260729-csa-styled-1.pdf); [Didit](https://didit.me/blog/eu-ai-act-deepfake-labelling-2026/) [SS]. A creator-oriented summary exists. — [ablefy](https://ablefy.io/en/eu-ai-act-zusammenfassung-fur-coaches-und-creator/) [SS, title]
- Veo outputs carry an invisible **SynthID** watermark. — [Google Cloud](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) [FT]. Per the guidance above, an invisible marker alone does not meet the visible-label requirement where Article 50(4) applies.

**France: copyright in AI outputs**
- French copyright (CPI art. L.111-1) protects a work only if it is **original**, meaning it bears the **imprint of the author's personality**. Originality requires **free, creative, formally identifiable human choices**.
- Creators should **document the creative process (prompts, revisions, aesthetic choices)**. Proof of human input can include the complexity of the intervention, **time spent on prompts**, and post-generation work such as editing or retouching software.
- In **February 2026** a **Munich court refused** copyright protection for three AI-generated logos for lack of predominant "human creative influence".

— all from the set [SNAC, AMF avril 2026](https://snac.fr/wp-content/uploads/2026/06/AMF-Avril-2026.pdf); [Fieldfisher (FR)](https://www.fieldfisher.com/fr/locations/france/insights/l%E2%80%99ia-et-la-propriete-intellectuelle-qui-possede-vo); [APIE / economie.gouv.fr](https://www.economie.gouv.fr/apie/quel-droit-dauteur-lere-de-lintelligence-artificielle-generative); [JDN](https://www.journaldunet.com/solutions/dsi/1525057-midjourney-stable-diffusion-generative-fill-comment-proteger-les-creations-visuelles-generees-par-ia/) [SS; attribution of each point within the set uncertain]. France's CSPLA has published a report on AI-generated works and copyright. — [Norton Rose Fulbright](https://connections.nortonrosefulbright.com/post/102o0bm/ai-generated-works-and-copyright-publication-of-a-report-by-the-cspla) [SS, title; date not seen]

**TikTok**
- AI content is allowed. The **AIGC label is a disclosure requirement, not a ban**.
- It is **required for content completely generated or significantly edited by AI that shows realistic-appearing people or scenes**. This includes synthetic faces, photorealistic AI environments, AI or cloned voices impersonating real people, and deepfakes or face-swaps.
- AI-written scripts, captions and voiceover tools are exempt.
- TikTok's labelling tool has existed since **19 September 2023**.

— [Cinerads: TikTok AI content policy 2026](https://www.cinerads.com/blog/tiktok-ai-content-policy); [ConductAtlas: TikTok guideline](https://conductatlas.com/platform/tiktok/tiktok-community-guidelines/ai-generated-content-labeling-requirement/); [AIVideoPicks](https://aivideopicks.com/posts/ai-generated-ads-disclosure-meta-tiktok-2026.html) [SS]. TikTok's own support page could not be opened.

**IP and characters**
- The Sora shutdown ended a reported **$1 billion Disney partnership**, which shows that major studios license character use deliberately and does not support free use of their characters. — [Engadget](https://engadget.com/ai/openai-is-shutting-down-its-sora-video-generation-app-211023358.html); [Zilliz](https://zilliz.com/ai-faq/what-is-the-sora-shutdown-timeline) [SS]

### Inferences
- **Beginner mistake checklist (and fixes):**
  1. Generating text-to-video shot after shot. Make keyframes first and animate only locked stills.
  2. No locked character or style. Make one reference sheet and one style-bible text block before anything else.
  3. Over-long or over-complex scripts (dialogue, crowds, hands, fights). Keep to 15–45 s with 4–10 simple shots.
  4. Tool overload. Use one LLM, one image tool, one video tool and one editor for the first month.
  5. Annual prepay or stacked subscriptions. Pay monthly, given price changes and the Sora shutdown.
  6. Ignoring sound. In wordless pieces, sound carries much of the emotion; plan it beat by beat.
  7. Upscaling or using 4K where TikTok playback doesn't need it.
  8. Chasing every new model release instead of finishing pieces.
- **Legal and ethical rules of thumb for a French hobbyist:**
  - Never use real people's faces or voices (friends, exes, celebrities). Realistic depictions of real people are what deepfake rules and TikTok target, and they create personal-rights risks.
  - Do not prompt protected characters or "in the style of [studio]" look-alikes (e.g. Disney, Pixar, Ghibli characters). Use original metaphor characters.
  - Turn on TikTok's AIGC label whenever the content looks realistic; doing so even for stylized content is cheap insurance.
  - Keep a dated log of prompts, selections and edits to support any claim of human authorship.
  - If the account later goes professional or is monetized, assume AI Act Article 50 labelling applies to anything that could pass as real.

### Gaps
- **Not verified this session (background knowledge only; the writer should verify before stating):**
  - French criminal law on non-consensual deepfakes, as amended by the **SREN law of 21 May 2024**: Code pénal art. 226-8 and the new art. 226-8-1 for sexual deepfakes, with higher penalties when published online.
  - The AI Act's exclusion of "**personal non-professional activity**" from the definition of "deployer" (Article 3(4)). This would likely put a purely private hobby TikTok outside Article 50(4).
  - The **lighter regime for "evidently artistic, creative, satirical, fictional" works** in Article 50(4): disclosure "in an appropriate manner that does not hamper the display or enjoyment of the work".
- **The 2026 status of studio lawsuits** against AI image and video firms over characters (e.g. Disney/Universal v. Midjourney, filed in 2025) was not verified.
- **Each tool's terms on output ownership and commercial use** (especially free tiers) and **music licensing** for AI-generated music (Suno, Udio) on TikTok were not researched successfully.
- **TikTok's official policy text and any 2026 changes** (e.g. automatic C2PA or Content Credentials detection, reach penalties for unlabelled AI content) were only seen through third-party summaries.
