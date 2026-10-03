# AI video generators for wordless, emotional TikTok micro-stories: models, capabilities, pricing and France/EU availability (as of 2026-10-03)

> **Method caveat for the report writer:** these notes are built only from web-search result summaries. Every direct page fetch was blocked by the network egress proxy, including official pricing pages, help centers, Artificial Analysis, Wikipedia and the Google blog. The session-wide web-search budget then ran out before **PixVerse, xAI Grok Imagine, Adobe Firefly Video, Moonvalley Marey and Lightricks LTX** could be researched. So every fact below is what the search summary of the cited page reported. Most cited pages are third-party guides dated 2026, and their exact publication dates were usually not visible. Treat prices and credit tables as indicative. Where sources conflict, the conflict is stated. Nothing in Cited Findings comes from memory. The few items from background knowledge are confined to Gaps and labelled "unverified".

---

## 1. Which models are state of the art right now (October 2026)? Latest versions and release dates

### Takeaway
2026 reshuffled the market. OpenAI **shut Sora down**: the app and web closed on 26 Apr 2026 and the API on 24 Sep 2026. Google replaced Veo 3.1 as its flagship with the "any-to-video" **Gemini Omni Flash**, launched 19 May 2026, followed by **Omni 1.1 Flash** on 27 Aug 2026. Chinese labs now hold the top of the blind-test leaderboards:
- **Alibaba:** HappyHorse-1.0 (April 2026) and **Wan 3.0** (24 Aug 2026).
- **MiniMax:** **H3 / "Hailuo 3.0"** (31 Jul 2026).
- **ByteDance:** Seedance 2.0 (Feb 2026) and **Seedance 2.5** (31 Jul 2026).
- **Kuaishou:** Kling 3.0 (5 Feb 2026). **Kling 4.0** was announced on 28 Sep 2026, with full launch scheduled for October 2026.

Runway (Gen-4.5, reportedly out of Artificial Analysis's top 10) and Luma (Ray3.2, ranking not found) are still active.

### Cited Findings
**OpenAI Sora (Sora 2 / Sora 2 Pro / Sora app): DISCONTINUED**
- Sora web and app experiences were discontinued on **26 April 2026**, and the Sora API on **24 September 2026**, in a two-stage shutdown — [OpenAI Help Center, "What to know about the Sora discontinuation"](https://help.openai.com/en/articles/20001152-what-to-know-about-the-sora-discontinuation); [The Decoder](https://the-decoder.com/openai-sets-two-stage-sora-shutdown-with-app-closing-april-2026-and-api-following-in-september/); [OpenAI Developer Community thread](https://community.openai.com/t/is-the-sora2-api-still-working/1379946)
- The shutdown was reported publicly around **25 March 2026**: "OpenAI pulls AI video app Sora as concerns grow on deepfake videos" — [Al Jazeera, 2026-03-25](https://www.aljazeera.com/economy/2026/3/25/openai-pulls-ai-video-app-sora-as-concerns-grow-on-deepfake-videos); [VentureBeat](https://venturebeat.com/technology/openai-is-shutting-down-sora-its-powerful-ai-video-app)
- **Conflict:** one site gives **29 April 2026** as the shutdown date — [restproperty.com](https://restproperty.com/news-en/innovacii/openai-shuts-down-sora-ai-video-tool-2026/). The OpenAI help article reportedly says 26 April.
- Reported reasons. These are secondary sources, not OpenAI statements, so treat them as unverified:
  - active users fell below 500,000 by early 2026;
  - heavy GPU costs;
  - about $2.1M in lifetime revenue;
  - copyright problems;
  - Disney pulling out of a content deal (one source says "$150M");
  - a pivot to coding/enterprise and AGI work.
  
  Sources: [techjournal.org](https://techjournal.org/what-happened-to-sora-openai-shutdown); [tech-insider.org](https://tech-insider.org/openai-sora-shutdown-disney-deal-ai-video-2026/); [Yahoo Finance](https://finance.yahoo.com/sectors/technology/articles/openai-killed-sora-ai-video-091159297.html)
- Sora reportedly continues only as a research project on world models — [Futurum Group](https://futurumgroup.com/insights/openai-sora-discontinuation-what-the-end-of-a-platform-means-for-enterprise-ai-strategy/) (search summary)

**Google: Veo 3.1 family, then Gemini Omni Flash**
- Veo 3 was released in **May 2025** and generates accompanying audio. **Veo 3.1 Lite** was announced for the Gemini API on **31 March 2026**. On **2 April 2026**, Google Vids gained Veo 3.1 video and Lyria 3 music — [Wikipedia: Veo](https://en.wikipedia.org/wiki/Veo_(text-to-video_model)); [Gemini API changelog](https://ai.google.dev/gemini-api/docs/changelog); [veo3ai.io](https://www.veo3ai.io/blog/google-vids-2026-update-veo-3-1-ai-music-avatars)
- **No Veo 4** had been announced as of 30 Aug 2026; Google DeepMind still calls Veo 3.1 its latest Veo model — [aireiter.com (Aug 2026)](https://aireiter.com/blog/veo-4); [queststudio.io (Aug 2026)](https://queststudio.io/blog/when-is-veo-4-coming-out); [evolink.ai](https://evolink.ai/blog/veo-4-release-date-2026)
- **Gemini Omni** was unveiled at Google I/O on **19 May 2026**, billed as "Google's first world model". **Gemini Omni Flash** launched that day as an any-to-video model with conversational editing. It is integrated into the Gemini app, YouTube Shorts creation tools and Google Flow — [Google blog: I/O 2026 announcements](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/); [Google blog: Gemini Omni videos](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni-3-5-videos/); [buildfastwithai](https://www.buildfastwithai.com/blogs/gemini-omni-google-ai-video-model-review); [bibigpt](https://bibigpt.co/blog/posts/gemini-omni-google-io-2026-world-model-video-vs-bibigpt)
- Gemini Omni Flash is described as "the replacement for Veo": editing-first, but also able to generate from text and references. It is "set to replace Veo in the Gemini app" — [Artlist Help Center](https://help.artlist.io/hc/en-us/articles/37099208586013-Gemini-Omni-Flash); [Artlist blog](https://artlist.io/blog/veo-3-1-vs-gemini-omni-flash-how-google-just-changed-the-way-you-edit-video/)
- **Gemini Omni 1.1 Flash** was released on **27 August 2026** and is available in the Gemini API, AI Studio, the Enterprise Agent Platform and, for AI Plus/Pro/Ultra subscribers, in **Google Flow** — [hyper.ai](https://hyper.ai/en/stories/d06021b7ade0362f40f0ac19be811d8d); [Google on X](https://x.com/Google/status/2093008576487072064); [Atlas Cloud](https://www.atlascloud.ai/blog/tips/what-is-gemini-omni-1.1-flash); [note.com/AIworker (Sept 2026 edition)](https://note.com/ai__worker/n/ne02d3b29cd70?hl=en)

**Kuaishou Kling**
- **Kling 3.0** launched on **5 February 2026**. It scored Elo 1,251 on the Artificial Analysis text-to-video benchmark at the time, which put it in the top three — [Wikipedia: Kling AI](https://en.wikipedia.org/wiki/Kling_AI); [Atlas Cloud Kling guide](https://www.atlascloud.ai/blog/guides/kling-ai)
- **Kling 3.0 Turbo and Kling 3.0 Omni** launched on **17 June 2026**, adding 4K editing, longer clips and the "Omni One engine" — [Atlas Cloud Kling 3.0 review](https://www.atlascloud.ai/blog/tips/kling-3.0-review-features-pricing-ai-alternatives); [rekreate.ai](https://rekreate.ai/models/kling-ai) (search summary)
- **Kling 4.0** was announced on **28 September 2026**:
  - A lighter **Kling 4.0 Flash** opened the same day to a limited group, starting with **Ultra yearly (annual) subscribers**.
  - The **full model launches in October 2026**.
  
  Sources: [Pandaily](https://pandaily.com/kling-ai-kling-4-0-30-second-native-video-multi-reference-control); [Futu News](https://news.futunn.com/en/post/1000311020/kuaishou-keling-releases-kling-4-0-up-to-30-seconds); [AI Weekly](https://aiweekly.co/alerts/kuaishous-kling-ships-kling-40-flash-to-annual-subscribers-30-second-4khdr-ai); [GuruFocus (Morgan Stanley note)](https://www.gurufocus.com/news/9100864/kuaishou-01024-set-to-launch-upgraded-kling-40-model-amid-analyst-caution); [fal.ai](https://fal.ai/learn/tools/what-is-kling-4-0)

**ByteDance Seedance (Dreamina / CapCut)**
- Seedance 2.0 went viral in early 2026 and was briefly paused under legal pressure from Hollywood studios. Disney accused ByteDance of "virtual piracy". The model was **relaunched globally with a ban on real-person face uploads** — [Phemex News](https://phemex.com/news/article/bytedance-relaunches-seedance-20-globally-with-restrictions-on-realface-uploads-68605); [Wikipedia: Seedance 2.0](https://en.wikipedia.org/wiki/Seedance_2.0)
- **Seedance 2.5** launched globally on **31 July 2026**, first on **Dreamina**. It is "now rolling out to **CapCut across Europe**, Asia, the Middle East and South America for subscriber accounts" — [Dreamina: Seedance 2.5 launch](https://dreamina.capcut.com/resource/seedance-2-5-launch); [PR Newswire](https://www.prnewswire.com/news-releases/dreamina-launches-seedance-2-5--the-tool-of-ai-video-generation-that-reduces-clip-stitching-visual-drift-and-rework-302841204.html); [Dreamina: Seedance 2.5 release date](https://dreamina.capcut.com/seedance/seedance-2-5-release-date); [CapCut: Seedance 2.5 for video editor](https://www.capcut.com/features/seedance-2-5-for-video-editor)
- A "Seedance 2.0 Fast" variant also exists and appears in leaderboards — [llm-stats.com](https://llm-stats.com/leaderboards/best-ai-for-video-creation)

**Alibaba: HappyHorse-1.0 and Wan 3.0 (new 2026 entrants)**
- **HappyHorse-1.0** is an Alibaba video model that topped benchmarks on release ("Alibaba's secret AI video model storms the benchmarks"). It surpassed Seedance 2.0 on the Artificial Analysis no-audio text-to-video board by **10 April 2026**, at Elo 1,374 versus 1,273 — [heise](https://heise.de/-11251074); [cutout.pro](https://www.cutout.pro/learn/?p=2924); [cutout.pro](https://www.cutout.pro/learn/?p=2914)
- **Wan 3.0** entered public beta on **6 August 2026** and was released on **24 August 2026**, a day after Alibaba's $10B share sale — [technology.org, 2026-08-24](https://www.technology.org/2026/08/24/alibaba-wan3-0-ai-video-model-share-sale/); [Alizila (Alibaba)](https://www.alizila.com/alibaba-unveils-wan3-0-with-twice-as-long-video-outputs-from-a-richer-variety-of-inputs/); [letsdatascience](https://letsdatascience.com/news/alibaba-launches-wan30-video-generation-model-2233eb30)

**MiniMax Hailuo: MiniMax H3 ("Hailuo 3.0", new in 2026)**
- MiniMax H3 was unveiled at WAIC on **17 July 2026** and released on **31 July 2026**. It is the third generation after Hailuo 01/02 and powers the Hailuo AI app. Its base weights were open-sourced on **3 August 2026** under a community license — [DataNorth](https://datanorth.ai/news/minimax-releases-minimax-h3); [Hugging Face blog](https://huggingface.co/blog/ResterChed/minimax-h3-hailuo-3-0); [vidmuse](https://vidmuse.ai/blog/hailuo-3-0)
- H3 is also offered inside "Luma Agents" — [orcarouter.ai](https://www.orcarouter.ai/blog/minimax-h3-hailuo-3-explained)

**Runway**
- **Gen-4.5** was released in **December 2025** and ranked #1 on the Artificial Analysis text-to-video board at launch, with Elo 1247 per one summary. **Native audio generation and audio editing were added in May 2026 via an ElevenLabs integration.** The search results showed no newer Runway video model ("Gen-5") — [AI Business](https://aibusiness.com/generative-ai/runway-releases-gen-4-5-video-model); [No Film School](https://nofilmschool.com/runway-gen-4-5-video-model); [Marketing AI Institute](https://www.marketingaiinstitute.com/blog/runway-top-ai-video-generation); [adcreate.com](https://adcreate.com/blog/runway-gen-4-5-review-features-pricing-2026)
- By September 2026, Gen-4.5 had reportedly "dropped out of the top 10" on Artificial Analysis — [Pinggy blog](https://pinggy.io/blog/best_video_generation_ai_models/); [vibedex](https://vibedex.ai/blog/best-ai-video-generator-2026) (search summary)

**Luma (Dream Machine)**
- **Ray3.14** ("Pi") was released in **January 2026** with native 1080p at 4× the speed of earlier versions. **Ray3.2** was released on **9 June 2026** and is Luma's newest model. Ray3.14 stays as the cheaper everyday option — [freeaitool.com](https://freeaitool.com/en/image-tools/003-luma-dream-machine-2026-complete-guide/); [fast.io](https://fast.io/resources/luma-ai-review-2026/); [kling4.co](https://www.kling4.co/blog/luma-ai-review-2026)

**ShengShu Vidu**
- **Vidu Q3** is the current model. It gained its own reference-to-video mode in **April 2026**. ShengShu also launched "Vidu Claw", an agent that turns one brief into a finished ad — [Atlas Cloud: Vidu Q3](https://www.atlascloud.ai/blog/ai-updates/vidu-q3-ai-video-generator-now-on-atlas-cloud-create-16s-cinematic-with-native-audio-sync); [PR Newswire APAC](https://en.prnasia.com/releases/global/shengshu-technology-unveils-vidu-claw-the-ai-cmo-that-turns-a-single-brief-into-a-finished-ad-532715.shtml)

**Pika**
- As of late February 2026, the production model is "Pika 2.5". In **August 2026** Pika launched the "Pika Audio" family (Soundtrack, Music, SFX, Speech) — [aitoolsdigest](https://www.aitoolsdigest.com/blog/latest-pika-ai-video-model-version-2026); [Pika blog](https://pika.art/blog)

**Midjourney Video**
- **Video V1** (image-to-video) launched on **19 June 2025**. The search found **no confirmed new video model in 2026**; the 2026 updates concern the V8/V8.1 image models (May 2026). Claims of V8 text-to-video at 10 s/60 fps appeared speculative — [Engadget](https://www.engadget.com/ai/midjourney-adds-ai-video-generation-192557140.html); [VideoProc](https://www.videoproc.com/resource/can-midjourney-make-videos.htm); [PixVerse blog: "Midjourney May 2026 Update: V8.1"](https://pixverse.ai/en/blog/midjourney-ai-image-generator-review)

**Unknown new entrant**
- **"Utopai X (based on MiniMax H3)"**, dated **September 2026**, sits at #2 on the Artificial Analysis T2V v2.0 board — [Artificial Analysis T2V leaderboard](https://artificialanalysis.ai/video/leaderboard/text-to-video). A dedicated search returned nothing about it.

### Inferences
- **Sora must be excluded from any recommendation.** It no longer exists as a consumer product, so features such as Sora "characters/cameos" are gone.
- **Google's current consumer video model is Gemini Omni (1.1) Flash, not Veo 4.** Veo 3.1, Fast and Lite remain selectable in Flow.
- **Kling 4.0 is brand new and gated.** It is due in October 2026, and Flash is currently limited to annual Ultra subscribers. A beginner starting now would realistically use **Kling 3.0 / 3.0 Turbo / Omni**, and should check whether 4.0 has reached lower tiers.
- Several 2026 leaders (Wan 3.0, MiniMax H3, HappyHorse) come with open weights or API-first distribution. Their consumer-app path for a French beginner is less obvious than Google's, Kling's or CapCut/Dreamina's.

### Gaps
- **Not researched because the search budget ran out:** PixVerse, xAI Grok Imagine, Adobe Firefly Video, Moonvalley Marey, Lightricks LTX. The background below is **unverified, from before 2026, and must not be stated as current**:
  - PixVerse V5 (Aug 2025) and V5.5 (Dec 2025, with audio and multi-shot);
  - Grok Imagine launched Aug 2025 and was involved in a Jan 2026 deepfake controversy with EU scrutiny;
  - Adobe's Firefly Video Model (2025) plus partner models inside the Firefly app;
  - Moonvalley Marey (Jul 2025, "licensed-data" model);
  - Lightricks LTX-2 (announced Oct 2025, open weights later).
  
  Their October 2026 versions are unknown.
- Who makes "Utopai X", and whether a consumer can use it, is unknown.
- I could not confirm whether OpenAI offers any replacement video generation inside ChatGPT.
- The figure for the Disney deal conflicts across reports ($150M in one secondary source); this is unverified.

---

## 2. Per-model capabilities: duration, resolution, 9:16, native audio, T2V/I2V, frame control, character references, multi-shot, camera, failure modes, watermark, rights, moderation

### Takeaway
The 2026 generation converged on the same set of features: native audio, multi-shot, multi-reference character consistency and keyframes. Maximum single-clip length grew from 8–10 s to 15–30 s:
- **Seedance 2.5:** 30 s, plus a 180 s beta mode.
- **Wan 3.0:** 30 s.
- **Kling 4.0:** 30 s, extendable to 2 minutes.
- **Omni 1.1 Flash:** 10 s clips, extendable to 40 s.

For a wordless story, the most relevant consistency features are:
- Seedance 2.5's 50 references;
- Kling 4.0's 15 references and 10 keyframes;
- Omni 1.1's video reference with first/last frames;
- Vidu Q3's 7 references;
- Luma Ray3.2's 16 keyframes.

Watermark rules, commercial rights per plan and 9:16 support could not be verified for most tools.

### Cited Findings
**Gemini Omni Flash / Omni 1.1 Flash (Google)**
- **Inputs:** text, image, audio or video. **Clips:** 4, 6, 8 or 10 s at 720p, with a **free 1080p upscale and native 4K**.
- It is described as the only video model with **native avatar generation**. It also offers inpainting, cleanup, swaps, motion graphics, style remixing and in-frame text tracking.

  Sources: [Artlist Help Center](https://help.artlist.io/hc/en-us/articles/37099208586013-Gemini-Omni-Flash); [invideo FAQ](https://invideo.io/faq/what-is-gemini-omni-flash-and-what-can-it-do/)
- **Conversational and voice-guided editing** with physics-aware output — [buildfastwithai](https://www.buildfastwithai.com/blogs/gemini-omni-google-ai-video-model-review); [bibigpt](https://bibigpt.co/blog/posts/gemini-omni-google-io-2026-world-model-video-vs-bibigpt)
- **What Omni 1.1 Flash (27 Aug 2026) adds:**
  - **scene extension** in 10 s increments up to **40 s total**, reading up to 10 s of prior context;
  - **first and last frame** control;
  - a **360p draft mode**, up to 60% faster at **one-third of the cost**;
  - native upscaling to 1080p/4K;
  - acceptance of **3 seconds of video reference to keep a character or style consistent**.

  Sources: [hyper.ai](https://hyper.ai/en/stories/d06021b7ade0362f40f0ac19be811d8d); [Segmind blog](https://blog.segmind.com/gemini-omni-1-1-flash-features-examples-and-1-0-compared/); [Google on X](https://x.com/Google/status/2093008576487072064)
- **Gemini app requires age 18+.** **Editing and extending uploaded videos is region-restricted in the EEA, Switzerland and the UK** — [The Rundown](https://www.therundown.ai/tools/gemini-omni); [geotoolbox](https://geotoolbox.ai/blog/gemini-omni)
- Omni Flash ranks on Artificial Analysis's "text-to-video with audio" board — [Hedra blog](https://www.hedra.com/blog/best-ai-video-models); [tech-insider](https://tech-insider.org/best-ai-video-generator-2026/)

**Veo 3.1 / Veo 3.1 Fast / Veo 3.1 Lite (Google, still available in Flow)**
- **Flow generation lengths:** Lite and Fast make 4, 6 or 8 s; Quality makes 8 s — [magichour.ai Flow pricing](https://magichour.ai/blog/google-flow); [diyai.io](https://diyai.io/ai-tools/video-generation/google-veo-pricing/)
- Veo 3 introduced native audio (May 2025) — [Wikipedia: Veo](https://en.wikipedia.org/wiki/Veo_(text-to-video_model))

**Kling 3.0 / 3.0 Turbo / Omni (Kuaishou)**
- **Modes:** 720p (Standard) and 1080p (Pro), each **with or without native audio**. There is an optional **"Voice Control"** add-on and a **multi-shot** mode at 720p, 1080p and 2160p (4K). The published credit table goes up to **15 s clips** — [eesel.ai](https://www.eesel.ai/blog/kling-ai-pricing); [vo3ai](https://www.vo3ai.com/kling-3-pricing); [kingy.ai Kling 3.0 review: "Multi-Shot, Native Audio & Limits"](https://kingy.ai/news/kling-3-0-review-a-serious-step-toward-ai-video-as-a-production-system/)
- 3.0 Turbo and Omni (June 2026) add 4K editing and longer clips — [Atlas Cloud](https://www.atlascloud.ai/blog/tips/kling-3.0-review-features-pricing-ai-alternatives)
- **Kling 4.0 (announced Sept 2026):**
  - **30 s** maximum single generation;
  - **multi-shot continuation up to 2 minutes**;
  - **up to 15 multimodal references** (text, images, existing video);
  - **up to 10 keyframes**;
  - output up to **4K / 10-bit HDR** with **stereo native audio**;
  - two versions, 4.0 and 4.0 Flash.

  Sources: [Pandaily](https://pandaily.com/kling-ai-kling-4-0-30-second-native-video-multi-reference-control); [Futu News](https://news.futunn.com/en/post/1000311020/kuaishou-keling-releases-kling-4-0-up-to-30-seconds); [AI Weekly](https://aiweekly.co/alerts/kuaishous-kling-ships-kling-40-flash-to-annual-subscribers-30-second-4khdr-ai)
- One listicle calls Kling 3.0 a specialist in **photorealistic people and natural movement**, among the best choices for social and story work (opinion) — [Unite.ai (Oct 2026)](https://www.unite.ai/best-ai-video-generators/); [Flowjam](https://www.flowjam.com/blog/best-ai-video-generators-2026)

**Seedance 2.5 (ByteDance; Dreamina, CapCut)**
- **Clips:** up to **30 s** as a single continuous clip, at **native 4K**, with built-in sound. A **Long Video Mode (beta)** goes up to **180 s** through multi-round generation.
- **References:** up to **50 multimodal references** per clip (images, video, audio, text).
- **Vendor claims:** "stronger character consistency", "reduces clip stitching, visual drift and rework".

  Sources: [Dreamina: Seedance 2.5](https://dreamina.capcut.com/seedance/seedance-2-5); [Dreamina: launch](https://dreamina.capcut.com/resource/seedance-2-5-launch); [PR Newswire](https://www.prnewswire.com/news-releases/dreamina-launches-seedance-2-5--the-tool-of-ai-video-generation-that-reduces-clip-stitching-visual-drift-and-rework-302841204.html)
- **Moderation (Seedance 2.0 onwards, on Dreamina):**
  - The model shows the note "**does not support real human faces**".
  - A face-detection classifier **rejects uploads containing photorealistic human faces** before generation. This includes your own face, strangers, people wearing glasses or helmets, and **even highly realistic AI-generated faces**.
  - **AI portraits, illustrated characters, 3D renders and stylized faces typically pass.**

  Sources: [MindStudio](https://www.mindstudio.ai/blog/seedance-2-0-content-restrictions-workarounds); [vicsee](https://vicsee.com/blog/seedance-content-filter); [X post by Alisa Qian](https://x.com/alisaqqt/status/2020877903102460321)
- Comparison sites contrast Dreamina's real-face moderation with Runway, which reportedly has "no real-people restriction" — [MindStudio](https://www.mindstudio.ai/blog/seedance-2-0-content-restrictions-workarounds) (search summary)

**Wan 3.0 (Alibaba)**
- **Modes:** text-to-video, image-to-video and reference-guided generation.
- **Output:** 480p, 720p or 1080p; **2–30 s**; aspect ratios **16:9, 4:3, 1:1, 3:4 and 9:16**; optional first-frame image; generates a matching audio track.
- **Inputs:** text, image, video and audio together, plus documents (PDF, PPT and others) and web URLs ("Omni-Reference"). Alibaba Cloud Model Studio describes single-pass 30 s at up to 1080p.

  Sources: [OpenRouter: Wan 3.0](https://openrouter.ai/alibaba/wan-3.0); [Morphic](https://morphic.com/resources/models/wan-3-0); [Alizila](https://www.alizila.com/alibaba-unveils-wan3-0-with-twice-as-long-video-outputs-from-a-richer-variety-of-inputs/); [explainx](https://explainx.ai/blog/alibaba-wan-3-0-video-model-august-2026)
- **Conflict:** one summary calls Wan 3.0 "open-weight" — [buildmvpfast (Sept 2026)](https://www.buildmvpfast.com/articles/best-llms-2026-guide/video-generation-ai). Other summaries describe it through Model Studio and API only. Unverified.

**HappyHorse-1.0 (Alibaba)**
- Outputs **native 1080p with synchronized audio**: multilingual lip-sync in 7 languages, **including French**, plus Foley sound effects. Supports text-to-video, image-to-video and video editing. Described as open-source and allowing commercial use. Surfaced on CapCut and Dreamina pages and on Hedra.

  Sources: [CapCut: Happy Horse](https://capcut.com/tools/happy-horse); [Dreamina review (nl)](https://dreamina.capcut.com/nl-nl/resource/happy-horse-review); [Hedra](https://mkt.hedra.com/video-models/happy-horse); [heise](https://heise.de/-11251074)

**MiniMax H3 / Hailuo 3.0**
- **Inputs:** text, images, video and audio read as one unified context.
- **Output:** up to **15 s of native 2K at 24 fps** with **native stereo audio** in the same pass.
- **Access:** API model ID `MiniMax-H3` and the Hailuo AI app. The Context-IR and 2K-regeneration modules are API-only.

  Sources: [DataNorth](https://datanorth.ai/news/minimax-releases-minimax-h3); [Hugging Face blog](https://huggingface.co/blog/ResterChed/minimax-h3-hailuo-3-0); [pexo.ai](https://pexo.ai/blog/what-is-minimax-h3-4020)

**Runway Gen-4.5**
- Gen-4 excelled at image-to-video. Gen-4.5 "pivots to text-to-video as its primary strength", with improved stylistic control, visual consistency and "controllable action generation". Native audio and audio editing arrived in May 2026 via ElevenLabs.
- One summary also claims "multi-shot sequencing and clip lengths up to 60 seconds". This comes from a single summary and is **unverified**.

  Sources: [adcreate.com](https://adcreate.com/blog/runway-gen-4-5-review-features-pricing-2026); [AI Business](https://aibusiness.com/generative-ai/runway-releases-gen-4-5-video-model)

**Luma Ray3.14 / Ray3.2**
- **Ray3.14:** native 1080p, 16-bit HDR, 24 fps, clips **up to 18 s**.
- **Ray3.2:** adds **up to 16 keyframes inside a single clip** (narrative beats, camera paths), "reasoning-driven" prompt adherence and 16-bit EXR export.
- **Dream Machine tools:** text-to-video, image-to-video, **start/end keyframes**, lip sync, inpainting and extension. **Ray3 Modify** handles video-to-video while preserving the original performance.

  Sources: [freeaitool.com](https://freeaitool.com/en/image-tools/003-luma-dream-machine-2026-complete-guide/); [fast.io](https://fast.io/resources/luma-ai-review-2026/); [gptprompts.ai](https://gptprompts.ai/luma-ai-guide); [aitoolradar](https://aitoolradar.io/guides/luma-dream-machine)

**Vidu Q3 (ShengShu)**
- Clips up to **16 s** with **native audio sync**, at 1080p — [Atlas Cloud](https://www.atlascloud.ai/blog/ai-updates/vidu-q3-ai-video-generator-now-on-atlas-cloud-create-16s-cinematic-with-native-audio-sync); [nemovideo](https://www.nemovideo.com/blog/what-is-vidu-q3)
- **Reference-to-video:** since April 2026, combines **up to 7 reference images or videos** (subjects, environments, costumes, props, style). The API endpoint accepts 1–4 reference images per call — [Atlas Cloud: Vidu Q3 API guide](https://www.atlascloud.ai/blog/tips/vidu-q3-api-guide); [Vidu platform pricing docs](https://platform.vidu.com/docs/pricing)

**Pika 2.5 / Pika Audio**
- Pika 2.5 claims objects stay stable across seconds and lighting stays consistent as the camera moves — [aitoolsdigest](https://www.aitoolsdigest.com/blog/latest-pika-ai-video-model-version-2026)
- The Pika 2.2 line added effects ("inflate", "deflate", "age", "de-age") and clips up to 10 s — [aitoolsdigest](https://www.aitoolsdigest.com/blog/latest-pika-ai-video-model-version-2026)
- **Pika Audio (Aug 2026):**
  - **Pika Soundtrack** turns a video into a synchronized full-scene soundscape;
  - **Pika Music** generates music;
  - there are also SFX and Speech models (voice cloning).

  Source: [Pika blog](https://pika.art/blog)

**Midjourney Video V1**
- Image-to-video only. Default 5 s, extendable by 4 s up to four times, to about **21 s**. Resolution is about **480p (SD) / 720p (HD)**. The Basic plan is limited to 480p; 720p requires a higher plan and Fast mode — [VideoProc](https://www.videoproc.com/resource/can-midjourney-make-videos.htm); [gamsgo](https://www.gamsgo.com/blog/midjourney-video-generator)

**Failure modes (vendor-acknowledged)**
- Vendors' 2026 launch messaging names the pain points they target, which indicates the typical failure modes of earlier models:
  - "clip stitching, visual drift and rework" (Seedance 2.5 PR) — [PR Newswire](https://www.prnewswire.com/news-releases/dreamina-launches-seedance-2-5--the-tool-of-ai-video-generation-that-reduces-clip-stitching-visual-drift-and-rework-302841204.html);
  - "AI video continuity and iteration speed" (Omni 1.1) — [hyper.ai](https://hyper.ai/en/stories/d06021b7ade0362f40f0ac19be811d8d).

### Inferences
Summary of verified capabilities. "?" means not verified in this session.

| Model (latest) | Max single clip | Extension / long mode | Max res | Native audio | 9:16 | Consistency tools |
|---|---|---|---|---|---|---|
| Gemini Omni 1.1 Flash | 10 s | to 40 s | 720p → 1080p/4K upscale | Yes (ranked on the "with audio" board) | ? (YouTube Shorts integration suggests yes) | 3 s video ref, first/last frame, avatars |
| Veo 3.1 (Fast/Lite/Quality) | 8 s | ? | ? | Yes (since Veo 3) | ? | ? |
| Kling 3.0 / Omni | 15 s | multi-shot | 1080p (4K in multi-shot/Omni) | Yes (optional, costs extra) | ? | multi-shot, elements (details ?) |
| Kling 4.0 (Oct 2026) | 30 s | to 2 min | 4K 10-bit HDR | Yes, stereo | ? | 15 refs, 10 keyframes |
| Seedance 2.5 | 30 s | 180 s (beta) | 4K | Yes | ? | 50 refs; **no photoreal face uploads** |
| Wan 3.0 | 30 s | — | 1080p | Yes | **Yes** | first frame, omni-reference |
| MiniMax H3 | 15 s | — | 2K | Yes, stereo | ? | multimodal refs |
| HappyHorse-1.0 | ? | — | 1080p | Yes (lip-sync incl. FR) | ? | ? |
| Runway Gen-4.5 | ? (60 s claim unverified) | ? | ? | Yes, since May 2026 | ? | references (details ?) |
| Luma Ray3.2 / 3.14 | 18 s (3.14) | extend | 1080p HDR | ? | ? | 16 keyframes, start/end frames |
| Vidu Q3 | 16 s | — | 1080p | Yes | ? | up to 7 refs |
| Midjourney V1 | 5 s | to ~21 s | 720p | No | ? | image-to-video only |

- For **wordless** stories, native dialogue and lip-sync (HappyHorse, Omni avatars) matter little. Native **ambience/SFX/music** is a nice-to-have, because TikTok lets creators add music in-app. **Kling bills audio as an option**: about 1.5× the price at 720p. A wordless creator can turn audio off to save credits.
- **Seedance's photoreal-face upload ban** makes a photoreal consistent protagonist built from a reference photo hard on Dreamina/CapCut. It does **not** affect stylized characters (anime, 3D/Pixar-like, clay, illustration), which suits stylized micro-stories.
- **Omni Flash's 10 s cap per generation**, extendable to 40 s, is enough for TikTok shots. Its "draft at 360p" mode is beginner-friendly for iterating cheaply.

### Gaps
- **9:16 support** was not verified for Omni Flash, Veo 3.1, Kling, Seedance 2.5, H3, Runway, Luma or Vidu. Only Wan 3.0 was confirmed. (Unverified background: Veo 3.1 got native vertical output and Kling/Seedance have long supported 9:16.)
- **Veo 3.1 feature details** were not re-verified for 2026: "Ingredients to video" (reference images), "Frames to video" and "Extend" in Flow. Unverified background: these were added in Oct 2025.
- **Kling "Elements" / multi-image reference** details for 3.0 were not retrieved, nor were camera-control features for any model.
- **Visible watermark rules** per plan were not found for any provider: Google SynthID / visible marks, Kling free tier, Dreamina free tier, Hailuo, Runway, Luma.
- **Commercial-use rights per plan** were not found for any provider. The only claim is that HappyHorse "supports commercial use", per an aggregator.
- **Moderation strictness** was found only for Seedance (strict face filter), Gemini (18+ and EEA editing restrictions) and Runway (reportedly no real-people restriction). Nothing was found for Kling, Hailuo, Vidu, Wan or Luma.
- Failure modes are documented only indirectly (vendor messaging). No independent failure-mode testing was retrieved, for example on hands, identity drift across shots or emotional micro-expressions.

---

## 3. Which models are best for (a) emotional acting, (b) stylized looks, (c) multi-shot consistency, (d) value, (e) beginners? Leaderboards and consensus

### Takeaway
Blind-test leaderboards are fragmented and changed scale in 2026, so rankings must be quoted with their date and board.

- **Artificial Analysis T2V v2.0 (with audio, 1080p, Sept 2026):** Wan 3.0 (1157), then "Utopai X" (based on MiniMax H3), **Seedance 2.5** and **MiniMax H3**.
- **Earlier 2026 AA snapshots:** HappyHorse-1.0 (April, no audio) and **Gemini Omni Flash** (mid-2026, with audio) at #1. Kling 3.0 and Veo 3.1 sat around #12–15.
- **Image-to-video:** H3 Max / Seedance 2.0 lead with audio; **Omni Flash leads the silent board** (1368).

Independent qualitative evidence on emotional acting and stylized looks was almost entirely missing.

### Cited Findings
**Leaderboards (blind human preference)**
- **AA-Video-T2V v2.0** ranks **text-to-video with audio** using pairwise human votes. AA-Video-I2V v2.0 is aligned with it, uses 1080p videos throughout and covers more models — [Artificial Analysis T2V v2.0](https://artificialanalysis.ai/video/leaderboard/text-to-video) (search summary)
- **AA T2V v2.0 top entries (Sept 2026):**
  1. **Wan 3.0**: Elo **1157 ±9** (Aug 2026)
  2. **Utopai X** (based on MiniMax H3): **1150 ±10** (Sep 2026)
  3. **Dreamina Seedance 2.5**: **1143 ±9** (Jul 2026)
  4. **MiniMax H3 (768p)**: **1138**
  5. **MiniMax H3 Max**: **1132**

  Sources: [Artificial Analysis embed](https://artificialanalysis.ai/embed/text-to-video-leaderboard/leaderboard/text-to-video); [Artificial Analysis](https://artificialanalysis.ai/video/leaderboard/text-to-video); [buildmvpfast (Sept 2026)](https://www.buildmvpfast.com/articles/best-llms-2026-guide/video-generation-ai)
- **Earlier AA snapshot**, probably June–August 2026 before v2.0 (date not stated in the summary):
  - **Gemini Omni Flash #1 at Elo 1,233** on T2V-with-audio;
  - **Kling 3.0 1080p (Pro) #12 (1095)**;
  - **Kling 3.0 720p (Standard) #13 (1089)**;
  - **Veo 3.1 #14 (1088)**;
  - **Veo 3.1 Fast #15 (1085)**.

  Sources: [Hedra blog](https://www.hedra.com/blog/best-ai-video-models); [tech-insider](https://tech-insider.org/best-ai-video-generator-2026/); [invideo: "Best AI Video Model in August 2026: Dated Arena Rankings"](https://invideo.io/blog/best-ai-video-model/). **Conflict:** this does not match the v2.0 numbers. The two boards probably use different scales and model sets, so do not mix them.
- **AA T2V without audio (spring 2026):**
  - HappyHorse-1.0 at Elo about **1364**, versus Seedance 2.0 at **1269** and Kling 3.0 Pro at **1244**;
  - on **10 April 2026**: HappyHorse 1,374 versus Seedance 1,273;
  - another snapshot: 1333 / 1273 / Kling 3.0 Pro 1241 (#4).

  Sources: [cutout.pro](https://www.cutout.pro/learn/?p=2924); [benchmarklist](https://benchmarklist.com/arenas/artificial_analysis_text_to_video/); [oakgen.ai](https://oakgen.ai/blog/happyhorse-vs-seedance-vs-kling-comparison)
- **AA image-to-video (latest seen):**
  - MiniMax H3 Max leads AA-Video-I2V v1.0 at **1195**;
  - **with audio**, Seedance 2.0 720p leads at **1191**;
  - **silent**, **Gemini Omni Flash** leads AA-Video-I2V-Silent v1.0 at **1368**;
  - among open-weights models, MiniMax H3 leads at **1181 ±8**;
  - in **June 2026**, HappyHorse-1.0 reportedly led I2V at **1,415**.

  Sources: [Artificial Analysis I2V](https://artificialanalysis.ai/video/leaderboard/image-to-video); [AA I2V open weights](https://artificialanalysis.ai/video/leaderboard/image-to-video/open-weights); [magichour I2V leaderboard](https://magichour.ai/model-leaderboard/image-to-video); [techsy.io](https://techsy.io/en/blog/best-ai-video-models)
- **Design Arena:** Gemini Omni Flash took **1st place overall** in the Video Arena, "7 places higher than" its best predecessor, Veo 3 Fast — [Artlist Help Center](https://help.artlist.io/hc/en-us/articles/37099208586013-Gemini-Omni-Flash); [Design Arena notes: "A Video Model for Directors"](https://notes.designarena.ai/gemini-omni-flash-a-video-model-for-directors/)
- **llm-stats.com arena (claimed "as of October 2026", different scale):** **Kling v3 at 1934**, then HappyHorse 1.0 at 1816 and Seedance 2.0 Fast at 1747 — [llm-stats.com](https://llm-stats.com/leaderboards/best-ai-for-video-creation). This is an aggregator board; its methodology was not verified.
- **Runway Gen-4.5** led AA at launch (late 2025, Elo 1247) but has "dropped out of the top 10" — [Pinggy](https://pinggy.io/blog/best_video_generation_ai_models/); [vibedex](https://vibedex.ai/blog/best-ai-video-generator-2026)

**Expert and listicle opinions (marked as opinions; affiliate-style lists)**
- "Best by use case" verdicts from an October 2026 listicle. **Caveat:** the same summary also lists "Runway Gen-3" and Sora as "top contenders", so parts of the page are stale.
  - "Best Overall": Google Veo 3, for prompt adherence and native audio in one render.
  - "Best Cinematic Realism": Veo 3.1.
  - **"Best Human Characters": Kling 3.0**, for photorealistic people and natural movement, "one of the best choices for marketing, social, or story work".
  - "Best for Commercial Speed": **Seedance 2.5**, 30 s with sound, 4K.
  - **"Best Value": Hailuo AI**, "top physics at the lowest cost per clip, with a genuinely usable free tier".
  - **"Best for End-to-End Storytelling": OpenArt**, an aggregator that turns a prompt, reference photo or song into a multi-scene video **up to 5 minutes with the same characters**.

  Sources: [Unite.ai, "10 Best AI Video Generators (October 2026)"](https://www.unite.ai/best-ai-video-generators/); [Flowjam (by use case)](https://www.flowjam.com/blog/best-ai-video-generators-2026); [OpenArt blog](https://openart.ai/blog/best-ai-video-generators/)
- Design Arena characterizes Omni Flash as "a video model for directors" — [Design Arena notes](https://notes.designarena.ai/gemini-omni-flash-a-video-model-for-directors/)
- Comparisons used for further reading but not opened: [Curious Refuge, Best AI Video Generators of 2026](https://curiousrefuge.com/blog/best-ai-video-generators-2026); [Zapier](https://zapier.com/blog/best-ai-video-generator/)

### Inferences
- **(a) Emotional acting and faces without dialogue:** the only explicit (opinion) evidence favours **Kling 3.0** for natural human performance. Top-ranked general-quality models such as Wan 3.0, Seedance 2.5, H3 and Omni Flash are plausible candidates, but no source specifically rated micro-expressions. Recommend Kling 3.0 / 4.0 and Omni Flash as the primary candidates, with a hedge.
- **(b) Stylized looks (anime, Pixar-like, clay, watercolor):** no ranking was found. Seedance (Dreamina/CapCut) is *structurally* suited to stylized characters, because its filter blocks photoreal faces but lets illustrated and 3D characters through. Midjourney's video is limited to 720p and roughly 21 s via extensions.
- **(c) Multi-shot consistency:** the strongest *feature sets* on paper are Kling 4.0 (15 refs, 10 keyframes, 2 min continuation), Seedance 2.5 (50 refs, 30 s single take, 180 s beta), Omni 1.1 Flash (video reference, first/last frame, 40 s extension), Vidu Q3 (7 refs) and Luma Ray3.2 (16 keyframes). These are vendor claims, not independently tested.
- **(d) Value:** see section 4. Google AI Pro/Plus with Flow credits and Kling (720p, audio off) look cheapest per second for subscribers. Vidu Q3 is cheapest per second via API at $0.05/s. Hailuo is cited as "best value" by a listicle.
- **(e) Beginners:**
  - **Gemini app / Flow:** conversational editing, EUR plans many French users already have, 18+.
  - **CapCut:** the editor TikTok creators already know, with Seedance 2.5 built in for subscribers in Europe.
  - **Aggregators (OpenArt, Higgsfield, Artlist, invideo, Hedra):** several models under one subscription. Their pricing was not researched.
- **The Artificial Analysis top 5 changed almost completely between April and September 2026.** Any ranking statement in the final report should carry its month.

### Gaps
- **No independent test was found focusing on wordless emotional acting**, micro-expressions or crying/smiling realism.
- **No comparison of stylized styles** (2D anime, Pixar-like 3D, claymation, watercolor) across models was retrieved.
- **Community sentiment was not captured** (r/aivideo, YouTube reviewers such as Theoretically Media and Curious Refuge, X filmmakers). Searches ran out before this.
- The current exact AA v2.0 positions of Omni (1.1) Flash, Kling 3.0/4.0, Veo 3.1, Runway, Luma and Vidu were not retrieved.

---

## 4. Pricing as of October 2026: free tiers, subscriptions, credits per clip, cost per second, API prices

### Takeaway
For a French subscriber, **Google AI Pro (€21.99/month, 1,000 Flow credits)** gives the lowest cost per second found among first-party consumer plans: Omni Flash at 15 credits per 10 s clip works out to about €0.03/s. **Kling** starts at about $6.99 for the first month, then $8.80/month (660 credits), and also gives 66 free credits per day; Kling 3.0 costs 6–12 credits per second. **Dreamina's Seedance 2.5** is the most expensive outside promotions, at about 37 credits per second at 720p, with conflicting per-second claims. **Runway's** Gen-4.5 rate is disputed (12 vs 25 credits/s). Most prices come from 2026 third-party guides and promotions are frequent, so verify on the official page before quoting.

### Cited Findings
**Google (France, EUR) and Flow credits**
- **France plan prices, as of 9 Sept 2026:**
  - Free;
  - **Google AI Plus: €4.99/month**;
  - **Google AI Pro: €21.99/month**;
  - **Google AI Ultra: from €99.99/month** (€219.99 for the highest tier).

  AI Pro includes **1,000 Flow credits** (per month) and YouTube Premium Lite. **Conflict:** storage is given as 2 TB in one source and 5 TB in another — [Finom (FR)](https://finom.co/fr-fr/blog/gemini-prix/); [Google: Google AI Pro & Ultra (FR)](https://gemini.google/fr/subscriptions/?hl=fr); [Jedha](https://www.jedha.co/formation-ia/abonnement-gemini-free-plus-pro-ultra); [gamsgo FR](https://www.gamsgo.com/fr/blog/gemini-pro-pricing)
- **AI Plus** includes access to **Gemini Omni Flash in Google Flow** — [Finom](https://finom.co/fr-fr/blog/gemini-prix/); [Jedha](https://www.jedha.co/formation-ia/abonnement-gemini-free-plus-pro-ultra)
- **Gemini app limits:** usage is compute-based, refreshing every 5 hours under a weekly cap. AI Plus gets 2× the standard limit, Pro 4×, and Ultra 5×–20× Pro depending on the Ultra tier. **No per-video quota is published** — [The Rundown](https://www.therundown.ai/tools/gemini-omni); [geotoolbox](https://geotoolbox.ai/blog/gemini-omni)
- **Flow credit costs per generation:**

  | Model | Clip | Credits (non-Ultra) | Credits (Ultra) |
  |---|---|---|---|
  | Veo 3.1 Lite | 4, 6 or 8 s | 10 | 5 |
  | Veo 3.1 Fast | 4, 6 or 8 s | 20 | 10 |
  | Veo 3.1 Quality | 8 s | 100 | 100 |
  | Gemini Omni Flash (720p) | 4 s / 6 s / 8 s / 10 s | 7 / 10 / 12 / 15 | ? |
  | Omni Flash video editing | per generation | 40 | ? |

  1080p upscaling is included for subscribers; **4K upscaling costs Ultra users 50 credits**.

  Sources: [magichour.ai](https://magichour.ai/blog/google-flow); [saascrmreview](https://saascrmreview.com/google-flow-pricing/); [diyai.io](https://diyai.io/ai-tools/video-generation/google-veo-pricing/); [toolcolumn](https://www.toolcolumn.com/pricing/google-flow-pricing)
- **Free access paths for Omni Flash (reported):** YouTube Shorts, the YouTube Create app and Flow's free tier. The free Gemini app shows Omni Flash "heavily rate-limited (a generation or two per day)" without the conversational editor or avatar mode — [findskill.ai](https://findskill.ai/blog/gemini-omni-free-access/); [bibigpt](https://bibigpt.co/blog/posts/gemini-omni-video-generation-vs-bibigpt-2026). A low-quality site claims "50 daily credits" free in Flow; this is unverified — [online-sciences.com](https://www.online-sciences.com/trending/google-flow-free-ai-videos/)
- **API pricing:** Omni Flash costs **$0.10 per second** of output, the same as Veo 3.1 Fast. Omni 1.1's 360p draft mode costs one-third of standard — [Artlist Help Center](https://help.artlist.io/hc/en-us/articles/37099208586013-Gemini-Omni-Flash); [hyper.ai](https://hyper.ai/en/stories/d06021b7ade0362f40f0ac19be811d8d)

**Kling (USD; global site)**
- **Plans:**

  | Plan | First month | Monthly renewal | Credits/month | Yearly price |
  |---|---|---|---|---|
  | Free (Basic) | — | — | **66 credits per day** | — |
  | **Standard** | **$6.99** | **$8.80** | **660** | $79.20 |
  | **Pro** | $25.99 | **$32.56** | **3,000** | $293.04 |
  | **Premier** | $64.99 | $80.96 | 8,000 | $728.64 |
  | **Ultra** | $127.99 | $159.99 | 26,000 | $1,429.99 |

  This gives about $1.33 per 100 credits on Standard, $1.09 on Pro, $1.01 on Premier and $0.62 on Ultra — [eesel.ai](https://www.eesel.ai/blog/kling-ai-pricing); [Atlas Cloud](https://www.atlascloud.ai/blog/tips/kling-ai-pricing); [createvision](https://createvision.ai/guides/kling-ai-pricing-2026); [techsifted](https://techsifted.com/reviews/kling-ai-pricing-2026/)
- **Kling VIDEO 3.0 credit rates** (per Kling's published guide, as relayed):
  - **6 credits/s** at 720p without audio;
  - **8 credits/s** at 1080p without audio;
  - **9 credits/s** at 720p with audio;
  - **12 credits/s** at 1080p with audio;
  - Voice Control adds 2 credits/s.

  Examples: 5 s at 720p without audio = 30 credits; 10 s at 1080p with audio = 120; 15 s at 1080p with audio = 180 — [eesel.ai](https://www.eesel.ai/blog/kling-ai-pricing); [vo3ai](https://www.vo3ai.com/kling-3-pricing)
- **Kling multi-shot rates** (720p / 1080p / 4K), from a third-party site and **unverified, oddly high**: 28/32/80 credits/s for 1–5 s; 25/28/70 for 6–10 s; 21/25/63 for 11–15 s — [vo3ai](https://www.vo3ai.com/kling-3-pricing) (search summary)
- Kling 3.0 Turbo has its own pricing page; the figures were not retrieved — [ImagineArt](https://www.imagine.art/blogs/kling-3-0-turbo-pricing)

**Dreamina / Seedance 2.5 (USD)**
- **Plans:** Basic **$15/month, 1,575 credits**; Standard **$35/month, 3,885 credits**; Advanced **$70/month, 8,645 credits**. **Conflict:** another source describes a **"$19 entry plan with 1,575 credits"** (about 5 Seedance 2.5 clips per month). The $15 figure may be an annual-billing equivalent — [Higgsfield blog](https://higgsfield.ai/blog/seedance-2-5-pricing-2026); [Atlas Cloud](https://www.atlascloud.ai/blog/tips/seedance-2.5-pricing-guide); [virse.ai](https://www.virse.ai/blog/how-much-is-seedance-2-5)
- **Per-clip cost:** a **720p 8 s Seedance 2.5 clip costs 296 credits (about $3.57)** — [Higgsfield blog](https://higgsfield.ai/blog/seedance-2-5-pricing-2026); [stevenvideo](https://www.stevenvideo.com/blog/seedance-2-pricing-guide)
- **Dreamina's own marketing:**
  - "Seedance 2.5 & 2.0 from $0.046/sec";
  - "from $0.097 per second on the compared annual plan";
  - a **promotion from 23 Sept to 9 Oct 2026**: 90% off the first month of the Basic monthly plan, giving **$0.035/s at 720p**, with a US introductory payment of $1.50.

  Sources: [Dreamina: Seedance price](https://dreamina.capcut.com/seedance/seedance-price); [Dreamina: Seedance 2.5 pricing](https://dreamina.capcut.com/seedance/seedance-2-5-pricing-2026); [Dreamina summer sale](https://dreamina.capcut.com/resource/dreamina-summer-sale-2026)

**Runway (USD, annual billing per user)**
- **Standard $12/month, 625 credits**; **Pro $28/month, 2,250 credits**; **Unlimited $76/month, 2,250 credits plus Explore Mode** (relaxed unlimited) — [eesel.ai](https://www.eesel.ai/blog/runway-ai-pricing); [magichour](https://magichour.ai/blog/runway-gen-45-pricing); [gptprompts](https://gptprompts.ai/runway-pricing)
- **Gen-4.5 credit cost conflict:** **12 credits/s** according to the most recent source (described as "3 days ago", i.e. about end of Sept 2026) versus **25 credits/s** in older articles — [techpresso academy](https://academy.techpresso.co/reviews/is-runway-worth-it); [magichour](https://magichour.ai/blog/runway-gen-45-pricing); [checkthat.ai](https://checkthat.ai/brands/runway/pricing)

**Hailuo (MiniMax), USD, with conflicting sources**
- **Source A** gives monthly prices: Free $0, Standard **$10.50**, Pro **$38**, Master **$89**, Max **$216**, with **1,000 / 4,500 / 10,500 / 27,000** credits. Yearly billing works out to $8.40, $30.40, $71.20 and $184 per month.
- **Source B** gives list prices of **$14.99, $54.99 and $94.99**, discounted to $7.99, $24.99 and $63.99.
- **Source C** gives Standard at $9.99/month for 1,000 credits.
- The **Free plan has no recurring monthly credits**, only one-time trial credits.

  Sources: [aiarty](https://www.aiarty.com/ai-video-generator/hailuo-ai-pricing.htm); [Atlas Cloud](https://www.atlascloud.ai/blog/tips/hailuo-ai-pricing-cost); [costbench ("Free–$199.99/month")](https://costbench.com/software/ai-video-generators/hailuo-ai/); [kingy.ai](https://kingy.ai/ai-tools/hailuo-ai/)
- **Hailuo 2.3 credits:** 768p 6 s = **25 credits**; 768p 10 s = **50**; 1080p 6 s = **50** (another source says **80**) — [aiarty](https://www.aiarty.com/ai-video-generator/hailuo-ai-pricing.htm); [Atlas Cloud](https://www.atlascloud.ai/blog/tips/hailuo-ai-pricing-cost)

**Vidu (API)**
- **Vidu Q3 Reference-to-Video:** **$0.05/s** at standard price; Q3-Mix R2V costs **$0.125/s**; Atlas Cloud offers it from $0.042/s — [Vidu platform pricing](https://platform.vidu.com/docs/pricing); [Atlas Cloud](https://www.atlascloud.ai/providers/shengshu)

**Price changes in 2025–2026 (only those documented)**
- Runway Gen-4.5 credit cost fell from 25 to 12 credits/s (reported) — [techpresso academy](https://academy.techpresso.co/reviews/is-runway-worth-it)
- Google's current France line-up has an AI Plus tier (€4.99) and several Ultra tiers ("from €99.99", up to €219.99) — [Finom](https://finom.co/fr-fr/blog/gemini-prix/). No sourced 2025 comparison was retrieved, so do not describe this as a price cut. Separately, Ultra pays half the Flow credits on Veo 3.1 Lite/Fast. This is a tier difference, not a dated change — [magichour](https://magichour.ai/blog/google-flow)
- Kling uses first-month discounts ($6.99 then $8.80) — [eesel.ai](https://www.eesel.ai/blog/kling-ai-pricing)

### Inferences
**Approximate cost per generated second** (calculated from the cited figures; ignores failed generations and any included plan perks):

| Route | Plan price | Credits | Model / setting | Credits per clip | ≈ cost per second | ≈ seconds per month |
|---|---|---|---|---|---|---|
| Google Flow | AI Pro €21.99 | 1,000 | Omni Flash 10 s (720p, 1080p upscale free) | 15 | **€0.033** | ~660 s (66 clips) |
| Google Flow | AI Pro €21.99 | 1,000 | Veo 3.1 Lite 8 s | 10 | €0.027 | ~800 s |
| Google Flow | AI Pro €21.99 | 1,000 | Veo 3.1 Fast 8 s | 20 | €0.055 | ~400 s |
| Google Flow | AI Pro €21.99 | 1,000 | Veo 3.1 Quality 8 s | 100 | €0.27 | ~80 s |
| Kling | Standard $8.80 | 660 | 3.0 720p, no audio | 6/s | $0.08 | ~110 s |
| Kling | Standard $8.80 | 660 | 3.0 1080p + audio | 12/s | $0.16 | ~55 s |
| Kling | Pro $32.56 | 3,000 | 3.0 1080p + audio | 12/s | $0.13 | ~250 s |
| Kling | Ultra $159.99 | 26,000 | 3.0 1080p + audio | 12/s | $0.074 | ~2,170 s |
| Kling | Free | 66/day | 3.0 720p, no audio | 6/s | $0 | ~11 s/day |
| Dreamina | Basic $19 (or $15) | 1,575 | Seedance 2.5 720p 8 s | 296 | $0.45 ($0.35) | ~42 s (5 clips) |
| Dreamina | Advanced $70 | 8,645 | Seedance 2.5 720p | 37/s | $0.30 | ~233 s |
| Runway | Standard $12 (annual) | 625 | Gen-4.5 @12 / @25 cr/s | — | $0.23 / $0.48 | ~52 s / ~25 s |
| Runway | Pro $28 (annual) | 2,250 | Gen-4.5 @12 / @25 cr/s | — | $0.15 / $0.31 | ~187 s / ~90 s |
| Hailuo | Standard ~$10 | 1,000 | 2.3 768p 6 s | 25 | ~$0.04 | ~240 s |
| Vidu Q3 API | pay-as-you-go | — | R2V | — | $0.05 | — |
| Omni Flash API | pay-as-you-go | — | standard / 360p draft | — | $0.10 / ~$0.033 | — |

**Notes on the table**
- The Kling free figure of about 11 s per day is equivalent to one 5 s 1080p-with-audio clip (60 credits) per day.
- The Dreamina rows conflict with Dreamina's own "from $0.046–0.097/s" claims, which likely refer to other models, resolutions or promotions. Flag this.

**Budget for one finished 60 s TikTok**
- Assumptions: 8 shots of about 8 s, with about 3 attempts per kept shot. That is about 24 generations, or about 190–240 s generated. The ×3 retry factor is an assumption, not a sourced figure.
- **Omni Flash in Flow:** 24 × 12 = 288 credits, so about **3 finished videos per month on AI Pro**.
- **Veo 3.1 Fast in Flow:** 480 credits, about 2 videos per month.
- **Veo 3.1 Quality:** about 2,400 credits, which exceeds AI Pro.
- **Kling 3.0 at 720p without audio:** about 1,150–1,440 credits, so Standard cannot cover one video while Pro covers about 2. At 1080p with audio, about 2,300–2,900 credits, roughly one Pro month.
- **Seedance 2.5 at 720p:** about 7,000 credits, roughly the Advanced plan ($70).
- **Runway Gen-4.5 at 12 credits/s:** about 2,300–2,900 credits, roughly one Pro month.

**For a wordless story,** turning native audio off (where billed separately, as on Kling) and adding music in TikTok/CapCut cuts generation cost by about 33%.

### Gaps
- **Missing pricing for several tools:**
  - **Luma** (Dream Machine plans, credits per Ray3.2/3.14 clip);
  - **Pika**: only an unverified "$8/mo" review headline — [heyfish.ai](https://heyfish.ai/pika-labs-review);
  - **Midjourney** plans;
  - **Vidu consumer plans**;
  - **MiniMax H3 credits per clip** in the Hailuo app;
  - **Wan 3.0 / HappyHorse** consumer or API per-second prices;
  - **Veo 3.1 API per-second prices**;
  - **PixVerse, Grok Imagine (SuperGrok), Adobe Firefly** (plans and partner-model credits), **Moonvalley, LTX Studio**.
- **Missing EUR prices** for Kling, Dreamina/CapCut, Runway, Hailuo and the others. Only Google's EUR prices were found. CapCut Pro price in France was not found.
- **Missing plan details:**
  - how many Flow credits AI Plus (€4.99) includes, and whether €4.99 is a promotional price;
  - what Ultra "from €99.99" includes;
  - whether Flow's free tier really gives about 50 daily credits in France;
  - whether Runway's Unlimited Explore Mode covers Gen-4.5;
  - Kling 4.0 credit pricing.
- **Free-tier details** (watermark, non-commercial status, resolution caps) were not found for any provider.
- **Dates:** most third-party pricing pages had no visible date. Treat them as "2026, exact date unknown". Google France prices are dated 9 Sept 2026 and the Dreamina promotion runs 23 Sept–9 Oct 2026.

---

## 5. Availability for a user in France/EU: app availability, age limits, VPN-only tools, Chinese apps' terms

### Takeaway
Google's tools are officially sold in France in EUR, and Gemini Omni Flash is available "globally" to 18+ subscribers. However, **editing and extending uploaded videos is blocked in the EEA**. **Seedance 2.5 is rolling out in CapCut across Europe** for subscribers, and Dreamina has localized European pages. Sora is **no longer available anywhere**; before it closed, French media reported it was not available in France without a VPN. No EU-specific information was found for Kling, Hailuo, Vidu, Wan or the other tools.

### Cited Findings
- **Sora 2 was not available in France** before the shutdown. French media wrote guides on accessing it in France, including via VPN, and earlier reported EU regulation as the cause of delays for the original Sora. Sora has since been discontinued globally (section 1). Sources: [Phonandroid](https://www.phonandroid.com/?p=2671667); [KultureGeek](https://kulturegeek.fr/?p=321275); [Journal du Geek (VPN)](https://www.journaldugeek.com/vpn/debloquer-sora-france/); [Mac4Ever](https://www.mac4ever.com/ia/187547-sora-debarque-en-france-ce-qu-il-faut-savoir-sur-l-ia-generatrice-de-video-d-openai); [Tenorshare FR](https://www.tenorshare.fr/iphone-tips/sora-nest-pas-disponible-dans-votre-pays.html)
- **Gemini Omni Flash in the Gemini app** is available to **Google AI Plus, Pro and Ultra subscribers globally, for users aged 18 and older**. **Editing and extending uploaded videos is region-restricted in the EEA, Switzerland and the UK** — [The Rundown](https://www.therundown.ai/tools/gemini-omni); [geotoolbox](https://geotoolbox.ai/blog/gemini-omni)
- **Google AI plans have official French pricing:** €4.99, €21.99 and from €99.99 — [Finom](https://finom.co/fr-fr/blog/gemini-prix/); [Google (FR)](https://gemini.google/fr/subscriptions/?hl=fr)
- **Gemini Omni 1.1 Flash** is available "globally" to Plus/Pro/Ultra subscribers in Flow — [hyper.ai](https://hyper.ai/en/stories/d06021b7ade0362f40f0ac19be811d8d)
- **Seedance 2.5** was released first on Dreamina and is **rolling out to CapCut across Europe** for subscriber accounts. It "appears as a selectable model as it becomes available in your region" — [Dreamina launch](https://dreamina.capcut.com/resource/seedance-2-5-launch); [CapCut feature page](https://www.capcut.com/features/seedance-2-5-for-video-editor)
- **Dreamina publishes localized European pages**, for example Dutch — [Dreamina (nl-nl)](https://dreamina.capcut.com/nl-nl/resource/happy-horse-review)
- **Seedance real-face policy** (relevant to EU users uploading their own likeness): photorealistic face uploads are rejected, including one's own face — [MindStudio](https://www.mindstudio.ai/blog/seedance-2-0-content-restrictions-workarounds); [Phemex](https://phemex.com/news/article/bytedance-relaunches-seedance-20-globally-with-restrictions-on-realface-uploads-68605)

### Inferences
- **The lowest-friction, fully official route for a French beginner** is Google (Gemini app or Flow, paid in EUR) and CapCut/Dreamina (TikTok's sister apps).
- The EEA restriction on Gemini only affects editing or extending **uploaded** videos. Generating from text or images should be unaffected, though this was not confirmed.
- **Under-18 users cannot use Gemini Omni Flash** in the Gemini app. Relevant if the end user is a minor.
- **Sora/VPN advice in older French articles is now obsolete.**

### Gaps
- **EU and France availability** was not verified for Kling (global site/app), Hailuo, Vidu, Wan/Qwen apps, HappyHorse, Luma, Runway, Pika, PixVerse, Grok Imagine, Adobe Firefly, Midjourney, Moonvalley or LTX. These include age limits and VPN requirements.
- **Chinese apps' terms** (data use, rights to generated content, jurisdiction) were not researched.
- Whether **YouTube Shorts' free Omni Flash / Veo features** and **Flow's free tier** work in France was not verified.
- **EU AI Act transparency obligations** for AI-generated content (Article 50) and **TikTok's AIGC labelling rules** were not researched. Unverified background: Article 50 obligations were scheduled to apply from 2 Aug 2026. Verify before stating.
- Whether **CapCut's European Seedance 2.5 rollout** has reached France specifically, and on which CapCut plan, was not confirmed.
