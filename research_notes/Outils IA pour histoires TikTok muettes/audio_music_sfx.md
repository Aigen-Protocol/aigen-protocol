# AI music, AI sound effects/foley and audio licensing for wordless emotional TikTok micro-stories (state as of 2026-10-03)

> **Reliability note for the report writer (read first).** Research date: 2026-10-03. The network proxy blocked direct page reads for almost every domain (suno.com, elevenlabs.io, blog.google, tiktok.com, support.google.com, capcut.com, pixabay.com, freesound.org, musicbusinessworldwide.com, wikipedia, the-decoder, invideo, etc.), and the shared web-search budget ran out partway through. As a result, **most findings below come from search-engine summaries of the cited pages, not from reading the pages myself**. Where one summary drew on several pages, I cite all the candidate pages together. **GitHub pages were read directly** (ACE-Step 1.5, YuE, AudioCraft/MusicGen, MMAudio, ThinkSound, HunyuanVideo-Foley and its LICENSE, LTX-2). Many prices come from third-party aggregators (costbench, toolradar, photutorial, etc.), not official pricing pages. Treat them as "reported" and re-check them on the vendor page before quoting a budget.
> Tags: **[primary]** = vendor/official page or a GitHub page I read; **[secondary]** = news site or aggregator; **[OLD >6 mo]** = information dated before about April 2026, so possibly outdated.

---

## Q1. Which AI music generators are best now (Oct 2026) for emotional instrumental/cinematic scoring, and what control do they give (mood, tempo, duration, structure, endings, video sync)?

### Takeaway
Three mainstream generators are current and usable for publishing:
- **Suno v6** (launched 2026-09-09). Accepts text, audio, image and video as input, can edit one section of a song, and has a Studio with stem export. Pro costs $10/month.
- **ElevenLabs Eleven Music v2** (May 2026). Trained on licensed data, supports section inpainting, and allows commercial use from the cheapest paid plan.
- **Google Lyria 3.5 / Lyria 3 Pro**, available in the free Flow Music app (formerly Producer.ai/Riffusion), the Gemini app and the API. Offers tempo and duration control, and outputs carry a SynthID watermark.

**Udio is not usable for publishing**: downloads have been off since 2025-10-30. For simple background scores with clean licensing, Soundraw, AIVA and Beatoven are cheaper and simpler. The best free local option with a clean license is **ACE-Step 1.5 (MIT license)**, which offers exact control of duration, BPM and key.

### Cited Findings

**Suno (market leader)**
- Suno v5.5 launched on 2026-03-26. Suno called it its "best and most personal model yet", with richer arrangements, sharper vocals and more dynamic sound — [Suno release notes](https://suno.com/release-notes); [TechJack Solutions](https://techjacksolutions.com/ai-tools/suno/suno-v5/)
- Suno introduced the v6 family on 2026-09-09:
  - **v6**: flagship, "reliable and precise"
  - **v6-wild**: for exploration, gives unexpected results
  - **v6-mini**: faster and more efficient, "available to everyone"
  - Sources: [AI Musicpreneur](https://www.aimusicpreneur.com/ai-tools-news/suno-v6-v6-wild-v6-mini-launch/); [musci.io](https://musci.io/blog/suno-v6-release-date); [eesel.ai](https://www.eesel.ai/blog/suno-v6-review); [Suno v6 page](https://suno.com/v6)
- Suno's own launch post: "Suno v6 is here. Turn images, videos, and voice memos into music. Make precise changes to songs you've already created. Explore more possibilities with v6-wild." — [Suno on X](https://x.com/suno/status/2097846245540888664) [primary]
- v6 is described as Suno's first generation "built with the music industry", using licensed catalogs from Warner Music Group, BMG and Believe. The BMG and Believe deals were not checked against a primary source — [AI Musicpreneur](https://www.aimusicpreneur.com/ai-tools-news/suno-v6-v6-wild-v6-mini-launch/); [musci.io](https://musci.io/blog/suno-v6-release-date) [secondary]
- As v6 rolls out, Suno is retiring its earlier models and moving entirely to v6 — [AI Musicpreneur](https://www.aimusicpreneur.com/ai-tools-news/suno-v6-v6-wild-v6-mini-launch/); [Choosely](https://choosely.ai/ai-radar/suno-v6-vs-v5-5-what-changed)
- In v6, video is an *input* used to make music, not an output. Suno does not render a finished video — [Pexo](https://pexo.ai/blog/what-is-suno-v6-5169)
- Editing features [secondary]:
  - Change a single section or lyric of an existing song with a plain-language instruction, leaving the rest intact
  - Combine several songs into a mashup in one request
  - Sample and isolate parts of a track
  - Sources: [PicLumen review](https://www.piclumen.com/blog/suno-v6-review/); [SiliconSense](https://siliconsense.club/guides/suno-v6); [Trust Node Logic](https://trustnodelogic.com/suno6.html)
- **Studio 2.0** adds MIDI support, stem separation and audio effects inside Suno. Premier subscribers can export 32-bit/48 kHz multitracks and stems from Studio without using a download — same sources; [Undetectr – Suno Studio review](https://undetectr.com/blog/suno-studio-review) [secondary]
- The flagship v6 and v6-wild require Pro ($10/month) or Premier ($30/month) — [roo.beehiiv](https://roo.beehiiv.com/p/suno-v6-features); [Layer3 Labs](https://www.layer3labs.io/guides/suno-pricing). One newsletter headline warns of a "96% credit trap" in v6; the details were not retrieved — [roo.beehiiv](https://roo.beehiiv.com/p/suno-v6-features)

**Udio (effectively a walled garden in 2026)**
- UMG settled its lawsuit with Udio (late Oct 2025) and announced a licensed AI music creation platform "launching in 2026" — [MBW](https://www.musicbusinessworldwide.com/universal-music-settles-udio-lawsuit-strikes-deal-for-licensed-ai-music-platform/); [Hypebeast](https://hypebeast.com/2025/10/umg-x-udio-settle-launch-licensed-ai-music-platform-in-2026) [OLD >6 mo]
  - It will be trained on authorized music and combine creation, consumption and streaming in one place.
  - Artists who opt in will be paid for training and for remixes of their songs.
- Udio suspended downloads on 2025-10-30. It then signed licensing deals with WMG (Nov 2025), Merlin (Jan 2026) and Kobalt (Apr 2026) — [Undetectr](https://undetectr.com/blog/udio-download); [Dynamoi](https://dynamoi.com/learn/ai-music-distribution/is-udio-music-still-downloadable). The Kobalt deal was reported as coming "ahead of 'new platform' launch" — [Digital Music News, 2026-04-09](https://www.digitalmusicnews.com/2026/04/09/udio-kobalt-deal/)
- As of Sept 2026, downloads are still off on every plan — [Undetectr](https://undetectr.com/blog/udio-review-2026); [SongCreator.pro](https://songcreator.pro/blog/suno-vs-udio); [Jack Righteous](https://jackrighteous.com/en-us/blogs/music-creation-process-guide/udio-ai-music-licensing-2026-creator-future)
  - Songs stay in the Udio library and can be played and shared through udio.com links.
  - You cannot export a stereo file or stems.
  - Udio "hopes" to bring back some form of download with the licensed platform, but has given no date or promise.
- Caution: one search summary dated the UMG–Udio settlement to "September 2026". The original coverage dates it to October 2025 — [EDM.com](https://edm.com/industry/umg-strikes-landmark-deal-udio-license-ai-music/); [Hypebeast](https://hypebeast.com/2025/10/umg-x-udio-settle-launch-licensed-ai-music-platform-in-2026)

**ElevenLabs Eleven Music**
- Presented as a "licensed-training" music model that went from v1 to v2 — [InVideo explainer (Aug 2026)](https://invideo.io/blog/elevenlabs-music-ai-generator/) [secondary]
- **Music v2 (May 2026)** added genre transitions and section inpainting, i.e. editable music — [ElevenLabs blog](https://elevenlabs.io/blog/introducing-music-v2); [BuildFastWithAI](https://www.buildfastwithai.com/blogs/elevenlabs-music-v2-review-2026)
- Alongside v2, ElevenLabs cut prices by up to 50% on the API and up to 40% on ElevenCreative self-serve plans — [ElevenLabs blog](https://elevenlabs.io/blog/introducing-music-v2); [InVideo](https://invideo.io/blog/elevenlabs-music-ai-generator/)
- Self-serve commercial use covers online and offline uses **except film, TV and studio games**; Enterprise plans cover all uses — [Glad-IA-tor](https://glad-ia-tor.com/tool/eleven-labs-music); [InVideo](https://invideo.io/blog/elevenlabs-music-ai-generator/)

**Google Lyria / Flow Music (Producer.ai and Riffusion absorbed into Google)**
- **Lyria 3** (2026-02-18), in beta in the Gemini app and "rolling out … for all":
  - Generates 30-second tracks.
  - Prompts can set genre and tempo.
  - **You can upload an image or a video and get a matching tune.**
  - Also available in YouTube's Dream Track.
  - Outputs carry a SynthID watermark, which you can check by uploading a file to Gemini.
  - Sources: [SiliconANGLE](https://siliconangle.com/2026/02/18/google-launches-lyria-3-music-generation-model/); [9to5Google](https://9to5google.com/2026/02/18/gemini-app-music-lyria-3/); [MBW](https://www.musicbusinessworldwide.com/google-just-launched-lyria-3-its-most-advanced-ai-music-generator-yet-in-the-gemini-app/); [Google Workspace Updates](https://workspaceupdates.googleblog.com/2026/02/create-custom-soundtracks-with-lyria-3.html); [Google blog](https://blog.google/innovation-and-ai/products/gemini-app/lyria-3/)
- **Lyria 3 Pro** (late March 2026):
  - Tracks up to 3 minutes, with structure control (intro, verse, chorus, bridge).
  - Accepts image input.
  - Available on the Gemini API, AI Studio and Vertex AI.
  - Priced at $0.08 per song ("Lyria 3 Pro Preview", as of Aug 2026), charged per output whatever the length.
  - Sources: [TechCrunch](https://www.techcrunch.com/2026/03/25/google-launches-lyria-3-pro-music-generation-model/); [Coverr](https://coverr.co/blog/google-lyria-3-pro-ai-music-generator-2026); [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/lyria-3-and-lyria-3-pro-on-vertex-ai); [Google blog](https://blog.google/innovation-and-ai/technology/ai/lyria-3-pro/); [OpenRouter](https://openrouter.ai/google/lyria-3-pro-preview); [BenchLM](https://benchlm.ai/media-pricing/lyria)
- **Google Flow Music**:
  - Google acquired ProducerAI (formerly Riffusion) in Feb 2026 and launched Flow Music as a standalone AI music studio on 2026-04-18.
  - Features: generate and remix full songs, **"Replace"** a section by text prompt, **"Extend"** a piece beyond its end, and make synced AI music videos with Veo.
  - Domain flowmusic.google; available in "more than 250 countries".
  - Sources: [Creative AI News](https://www.creativeainews.com/blog/google-flow-music-launch-lyria-3-ai-studio/); [KOCPC](https://en.kocpc.com.tw/archives/3683); [TestingCatalog on Threads](https://www.threads.com/@testingcatalog/post/DXP82AgjZ4W/google-officially-announced-flow-music-an-ai-music-generation-tool-powered-by)
  - Flow Music later added song generation, editing and **stem splitting** to Google's "Spaces" tool — [MBW](https://www.musicbusinessworldwide.com/googles-flow-music-adds-song-generation-editing-and-stem-splitting-to-spaces-its-vibe-coding-tool/)
- **Lyria 3.5** (2026-07-29), released inside Flow Music and **free for all Flow Music users**:
  - Full songs up to 3 minutes.
  - Improvements to structure, instruction following, vocals, and **tempo and duration control**.
  - SynthID watermark on all outputs.
  - Sources: [TUN](https://www.tun.com/home/google-deepmind-launches-lyria-3-5-in-flow-music-ai-music/); [MLQ](https://mlq.ai/news/google-releases-lyria-35-in-flow-music-with-upgraded-vocals-and-song-controls/); [SoundStock](https://www.soundstock.com/news/2026-07-29-google-launches-lyria-3-5-music-generation-model-in-flow-music); [Emergent](https://emergent.sh/news/google-lyria-3-5-launches-flow-music-advanced)
- Riffusion was discontinued on 2026-08-02 and riffusion.com now redirects to "flowmusic.app". Flow Music's pricing page could not be checked automatically — [AI Creators Tools](https://aicreators.tools/voice-audio/music-generators/riffusion); [CodaOne](https://www.codaone.ai/tools/riffusion/). Note the domain conflict: flowmusic.google versus flowmusic.app.

**Stable Audio 3.0 (Stability AI)**
- Released 2026-05-20 as four models — [MBW](https://www.musicbusinessworldwide.com/stability-ai-launches-new-audio-models-that-can-generate-6-minute-music-tracks/); [MindStudio](https://www.mindstudio.ai/blog/what-is-stable-audio-3-stability-ai); [KJWL](https://www.kjwl.com/2026/05/20/stability-ai-launches-improved-music-models/):
  - **Small SFX**: sound effects on phones and laptops
  - **Small**: full music composition on-device
  - **Medium**: tracks up to 6 min 20 s
  - **Large**: for platforms and high-volume use
  - Small SFX, Small and Medium are open-weight on Hugging Face.
- Trained exclusively on licensed data: 806,284 AudioSparx recordings and 472,618 Freesound Creative Commons recordings — [AIToolTier](https://aitooltier.com/tools/stable-audio); [ChatForest](https://chatforest.com/reviews/stability-ai-stable-audio-3-open-weight-music-sfx-generation/)
  - Produces stereo instrumental audio with variable length.
  - Supports audio inpainting and LoRA customization.
- For comparison, Stable Audio 2.0 (Apr 2024) was limited to 3 minutes — [Stability AI](https://stability.ai/news/stable-audio-2-0) [OLD >6 mo]

**Mureka (Kunlun Tech)**
- V8 ("Supermodel") was released on 2026-01-28. Its instrumental mode draws on a library of 100+ instruments (piano, strings, brass, synths, ethnic instruments) — [Gaga.art](https://gaga.art/blog/mureka-v8/) [secondary, promotional tone]
  - Conflicting version history: another review says V9 came out in January 2026 and the consumer V9 in late March 2026 — [HookGenius](https://hookgenius.app/learn/mureka-ai-review/)
- **V9.5** was officially released in Aug 2026 (press release dated 2026-08-31) — [GlobeNewswire](https://www.globenewswire.com/news-release/2026/08/31/3353336/0/en/mureka-introduces-next-generation-ai-music-model-v9-5-advancing-toward-more-human-like-song-creation.html) [primary]; [Pandaily](https://pandaily.com/mureka-v9-5-ai-music-kunlun-tech-jul2026)
  - Built on a "MusiCoT" (music chain-of-thought) framework.
  - Adds "O3 reflective music reasoning" (iterative refinement) and "MuCo", a creation agent with version control.
  - Claims "richer emotional depth" and more cohesive arrangements.

**"Royalty-free background music" generators (simpler licensing; prices in Q6)**
- **Soundraw**: tracks created while subscribed stay licensed for life, even after you cancel — [CostBench](https://costbench.com/software/ai-music-generators/soundraw/); [Toolradar](https://toolradar.com/tools/soundraw/pricing) [secondary]
- **AIVA**: Standard plan allows tracks up to 5 minutes, with MP3 and MIDI downloads — [CostBench](https://costbench.com/software/ai-music-generators/aiva/); [Tooliverse](https://tooliverse.ai/tools/aiva) [secondary]
- **Beatoven.ai**: Maestro model (Aug 2025) at 44.1 kHz, with "superior instrument layering" and "more nuanced emotional transitions". Also offers Maestro SFX generation — [CostBench](https://costbench.com/software/ai-music-apis/beatoven-ai/); [Tooliverse](https://tooliverse.ai/tools/beatoven-ai) [secondary; Maestro launch OLD >6 mo]

**Open-source / local models**
- **ACE-Step 1.5** (ACE Studio + StepFun) — [GitHub](https://github.com/ace-step/ACE-Step-1.5) [primary, read]:
  - **MIT license**.
  - Generates 10 s to 10 min of audio.
  - Metadata control of **duration, BPM, key/scale and time signature**.
  - Cover, repaint (selective editing) and LoRA training.
  - "1000+ instruments and styles".
  - The XL variant (4B-parameter DiT) was released on 2026-04-02.
  - VRAM: minimum ≤6 GB (2B turbo model, quantized); 12 GB+ for XL.
  - The README asks users to "clearly disclose AI involvement".
  - Aggregators claim it runs on under 4 GB of VRAM and was trained on royalty-free, non-copyrighted material. The README does not state the training-data claim — [Communeify](https://www.communeify.com/en/blog/ace-step-1-5-opensource-ai-music-generator-4gb-vram/); [DEV Community](https://dev.to/czmilo/ace-step-15-the-complete-2026-guide-to-open-source-ai-music-generation-522e)
- **YuE2** (M-A-P / HKUST team) — [GitHub YuE](https://github.com/multimodal-art-projection/YuE) [primary, read]:
  - Code under Apache 2.0; weights under CC BY-NC 4.0 "with creator permission".
  - Personal users and content creators may "use YuE2 and monetize generated outputs, with no fees or royalties". Companies need a commercial license.
  - Instrumental generation was added on 2026-09-25; the paper was published 2026-09-29.
  - Needs an NVIDIA GPU with 24 GB VRAM.
  - Free online demo at yue.noizai.net.
- **Meta MusicGen / AudioGen** (AudioCraft): code under MIT, but **weights under CC-BY-NC 4.0, which prohibits commercial use** — [GitHub AudioCraft](https://github.com/facebookresearch/audiocraft) [primary, read]

**Video-to-music and exact length (summary of the sources above)**
- **Image or video → music:**
  - Suno v6 (video, image and voice-memo inputs)
  - Lyria 3 in the Gemini app (image or video upload, 30 s)
  - Lyria 3 Pro (image input)
  - Adobe Firefly "Generate music for videos" (upload a video) — [Adobe HelpX](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-audio/generate-soundtrack-for-an-uploaded-video.html)
  - Mirelo (video → SFX, ambience and music; see Q3)
- **Length and ending control:**
  - ACE-Step 1.5 (duration metadata)
  - Lyria 3.5 (duration and tempo control)
  - Stable Audio 3 (variable length, inpainting)
  - Suno v6 (section edits)
  - ElevenLabs Music v2 (section inpainting)
  - Flow Music (Replace and Extend)

### Inferences
- Micro-stories are about 10–60 s long. The most useful features are therefore: (a) an instrumental mode, (b) the ability to rework only the ending or the climax, and (c) length control. All three are now covered by Suno v6 section edits, ElevenLabs v2 inpainting, Flow Music Replace/Extend and Lyria 3.5 duration control.
- Lyria 3 in the Gemini app (30-second clips from an uploaded video or image) is almost made for TikTok-length cues. However, its commercial terms and EU availability were not verified (see Gaps).
- Udio should be left out of a beginner's toolkit until its licensed platform ships with downloads.
- Open-source music generation only makes sense if the user has an NVIDIA GPU with about 6–24 GB VRAM:
  - ACE-Step (MIT) is license-clean.
  - YuE2 allows individual creators to monetize.
  - MusicGen weights are non-commercial.
- The industry is clearly moving toward licensed training: Suno v6 (WMG and others), ElevenLabs, Stable Audio 3 (AudioSparx/Freesound) and Udio's coming platform. This should reduce, but does not remove, the risk of claims.

### Gaps
- **Quality comparisons**: I gathered no blind tests or community verdicts (r/SunoAI, r/udiomusic, r/aivideo, YouTube reviewers) on quality for cinematic, orchestral, piano, lo-fi or ambient instrumental work, because the search budget ran out. Quality statements above are vendor or aggregator claims.
- **Suno v6**:
  - Exact credit cost per v6 or v6-wild generation (the "96% credit trap")
  - Maximum song length and maximum video-input length
  - Whether there is an explicit BPM or duration parameter
  - Price of extra downloads
- **Eleven Music**:
  - Maximum track length, credits per minute in the web app, and whether stems can be exported
  - Licensing partners: Merlin and Kobalt deals were announced at the Aug 2025 launch according to my background knowledge, but not verified here.
- **Lyria and Gemini app**:
  - Whether music generation is available in France/EU
  - Age limits
  - Commercial-use terms for outputs from the Gemini app and from Flow Music
  - Status of Lyria RealTime
  - Flow Music pricing and credits
- **Mubert, Loudly, Soundful, MusicGPT**: no current information retrieved on versions, prices or licenses.
- **Beatoven**: whether its video-to-music feature still exists in 2026.
- **Stable Audio 3**: license of the open weights (probably the Stability AI Community License, but not confirmed) and stableaudio.com consumer prices.

---

## Q2. Commercial rights and platform safety: who grants commercial rights, how the 2025–26 label deals changed Suno and Udio, Content ID, monetized TikTok use, and the risks of copyrighted songs

### Takeaway
Since **2026-09-03, Suno grants commercial rights only for songs downloaded while on a paid plan, within the monthly cap**: 20 downloads/month on Pro, 60 on Premier. Free-tier songs are personal-use only. Udio songs cannot leave Udio at all. ElevenLabs, AIVA, Beatoven, Soundraw and Mureka grant commercial use on paid plans. AIVA's cheapest paid plan explicitly covers monetized TikTok use while AIVA keeps the copyright.

On the platform side:
- Fully AI-generated music **cannot be registered in YouTube Content ID**, but it can still be claimed if it resembles an existing work.
- TikTok requires an **AI-generated content (AIGC) label** for realistic AI content.
- TikTok's Creator Rewards Program (CRP) requires original content and (according to secondary sources) videos of 60 s or more. Short wordless micro-stories would therefore not earn CRP money anyway.

### Cited Findings

**Suno after the Warner Music Group (WMG) deal**
- WMG settled its copyright lawsuit and signed a licensing deal with Suno, announced on 2025-11-25 — [MBW](https://www.musicbusinessworldwide.com/warner-music-group-settles-with-suno-strikes-first-of-its-kind-deal-with-ai-song-generator/); [Music Ally](https://musically.com/2025/11/25/ai-music-firm-suno-strikes-first-licensing-deal-with-warner-music-group/); [Hollywood Reporter](https://www.hollywoodreporter.com/music/music-industry-news/warner-music-group-settles-ai-infringement-suit-with-suno-1236435516/) [announcement OLD >6 mo; implemented during 2026]. Announced changes for 2026:
  - New, licensed models, with current models phased out
  - Downloading audio requires a paid account
  - Free-tier songs are not downloadable, only playable and shareable
  - Paid tiers get monthly download caps, with the option to pay for more
- The deal also lets users legally use the voices and likeness of WMG artists who opt in — [Interesting Engineering](https://interestingengineering.com/culture/warner-music-suno-artist-likeness-deal)
- **Download caps since 2026-09-03**: Free = 7 downloads lifetime; Pro = 20/month; Premier = 60/month — [MuseGen](https://www.musegen.ai/blog/suno-download-limits-what-changed-alternatives); [Replayed Studio](https://replayedstudio.com/blog/ran-out-of-suno-downloads/). *Conflict*: the WMG announcement said free-tier songs would not be downloadable at all.
- **Terms effective 2026-09-03** — [Dynamoi](https://dynamoi.com/learn/ai-music-distribution/suno-commercial-rights-explained); [Veena Studio](https://www.veena.studio/blog/suno-commercial-use-rules); [MuseGen](https://www.musegen.ai/blog/suno-download-limits-what-changed-alternatives):
  - The help article on paid rights now says "Songs downloaded while subscribed are granted commercial use rights".
  - You may commercially exploit a Pro or Premier song only once you have downloaded it through Suno, within your plan's allocation.
  - Output that was not downloaded through an approved channel may not be commercially exploited.
  - Free-plan songs and trial downloads remain personal-use only.
- **Free plan**: Suno keeps ownership and grants a personal, non-commercial license — [Terms.law](https://terms.law/ai-output-rights/suno/); [Music in Africa](https://musicinafrica.net/magazine/suno-adjusts-ai-music-ownership-terms-after-warner-music-partnership/)
  - Not allowed: distribution to streaming services, monetized YouTube videos, client work, sync.
  - Songs made without an active subscription "cannot be monetised, even if a user later subscribes".
- The earlier paid-plan wording was "If you are a subscriber to a paid plan, you own the Outputs you generate…" — [Terms.law forum](https://terms.law/forum/thread/suno-ai-music-commercial-license.html). Music in Africa reports that Suno "adjusted AI music ownership terms" after the WMG partnership — [Music in Africa](https://musicinafrica.net/magazine/suno-adjusts-ai-music-ownership-terms-after-warner-music-partnership/). *The current wording appears to grant "commercial use rights" (a license) rather than ownership. This conflict is unresolved; verify on Suno's terms page.*

**Udio**
- Downloads have been disabled since 2025-10-30 and were still off in Sept 2026. Tracks can only be played or shared inside Udio, so a user cannot legally get an Udio track into a video editor — [Undetectr](https://undetectr.com/blog/udio-download); [Dynamoi](https://dynamoi.com/learn/ai-music-distribution/is-udio-music-still-downloadable); [SongCreator.pro](https://songcreator.pro/blog/suno-vs-udio)

**Rights on other music tools**
- **ElevenLabs**:
  - Commercial rights start at the Starter plan — [Gradually.ai](https://www.gradually.ai/en/elevenlabs-pricing/)
  - Self-serve plans exclude film, TV and studio games; Enterprise covers everything — [Glad-IA-tor](https://glad-ia-tor.com/tool/eleven-labs-music)
  - Marketed as "cleared for commercial use from day one — no sync fees" — [InVideo](https://invideo.io/blog/elevenlabs-music-ai-generator/) [secondary]
- **AIVA** — [CostBench](https://costbench.com/software/ai-music-generators/aiva/); [Tooliverse](https://tooliverse.ai/tools/aiva):
  - Standard (€11/month, billed annually): AIVA keeps the copyright, but you may monetize on **YouTube, Twitch, TikTok and Instagram** without crediting AIVA.
  - Pro (€33/month, billed annually): copyright transfers to you and use is unrestricted.
- **Beatoven**: paid plans include an "exclusive music license" — [CostBench](https://costbench.com/software/ai-music-apis/beatoven-ai/)
- **Soundraw**: the Creator plan is "royalty-free for videos, podcasts, ads, and client work"; tracks stay licensed for life after cancelling — [CostBench](https://costbench.com/software/ai-music-generators/soundraw/); [Toolradar](https://toolradar.com/tools/soundraw/pricing)
- **Mureka**: the Pro plan includes "full commercial rights" — [Gaga.art](https://gaga.art/blog/mureka-v8/) [secondary]
- **Google Lyria 3 / 3.5**: every output carries a SynthID watermark — [SiliconANGLE](https://siliconangle.com/2026/02/18/google-launches-lyria-3-music-generation-model/); [MLQ](https://mlq.ai/news/google-releases-lyria-35-in-flow-music-with-upgraded-vocals-and-song-controls/)

**Content ID and AI music**
- As of July 2025, fully AI-generated audio is not eligible for YouTube Content ID. You can monetize your own videos that use Suno music, but you cannot register the audio to claim other people's uses — [Jack Righteous](https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/can-you-monetize-suno-ai-music-on-youtube-heres-what-you-need-to-know); [GenX Notes](https://genxnotes.com/en/posts/can-you-get-youtube-content-id-on-suno-generated-ai-music/) [OLD >6 mo]
- Most distributors will not register Suno tracks for Content ID. LANDR lists YouTube Content ID, Meta, TikTok, Deezer, Pandora and Tencent among destinations that do not receive its AI-generated music — [Dynamoi](https://dynamoi.com/learn/ai-music-distribution/distributors-that-accept-ai-music); [Jack Righteous](https://jackrighteous.com/en-us/blogs/ai-music-distribution-guide/ai-music-distribution-rules-distrokid-spotify-apple-deezer)
- An AI track that sounds close to an existing song (through training-data leakage) can trigger a takedown or claim, whatever the generator's terms say. This has reportedly already happened to creators on YouTube and TikTok — [NisAI](https://nisai.dev/guides/ai-music-generation-2026/); [HookGenius](https://hookgenius.app/learn/suno-legal-guide/) [secondary]

**TikTok rules on AI content and monetization**
- **AIGC labels** are required for: photorealistic AI-generated people or scenes; AI voice or audio that impersonates a real person; and fully AI-generated photorealistic scenes presented as if filmed. The policy is about disclosure, not prohibition — [Cinerads](https://www.cinerads.com/blog/tiktok-ai-content-policy); [Storrito](https://storrito.com/resources/tiktoks-2026-ai-labeling-rules-and-what-they-signal-for-platform-governance/)
- TikTok uses **C2PA Content Credentials** to detect AI media automatically, having been the first video platform to adopt them on 2024-05-09 [OLD >6 mo]. It has announced automatic labeling for audio-only media; the rollout date was not found — [Storrito](https://storrito.com/resources/tiktoks-2026-ai-labeling-rules-and-what-they-signal-for-platform-governance/); [CoinGeek](https://coingeek.com/tiktok-new-update-to-automatically-label-ai-generated-content/)
- On 2026-07-10, TikTok said it had labeled more than 3 billion videos as AIGC, up from 1.3 billion in Nov 2025 — [Kompozy](https://kompozy.io/guides/tiktok-ai-labeling-at-scale)
- **Creator Rewards Program (CRP)**:
  - TikTok's official wording, seen only in a search summary: content must "be original and produced entirely by the creator and/or adds new ideas to preexisting content, be high quality as determined by TikTok in its sole discretion…" — [TikTok Support](https://support.tiktok.com/en/business-and-creator/creator-rewards-program/creator-rewards-program)
  - An EEA-specific version of the CRP terms exists — [TikTok CRP Terms (EEA)](https://www.tiktok.com/legal/page/global/tiktok-creator-rewards-program-eea/en) (could not be read)
  - Secondary sources say the CRP **excludes fully AI-generated content or content with "minimal original input"**, while AI-assisted workflows (color correction, captions, AI B-roll) stay eligible — [Storrito](https://storrito.com/resources/what-tiktoks-ai-monetization-restrictions-signal-for-creator-income/); [CreatorsAgency](https://creatorsagency.co/blog/tiktok-creator-rewards-program-2026) [secondary; not confirmed in official text]
  - Failing to label AI content reportedly leads to escalating penalties: removal, then posting restrictions, then permanent removal from the program after a 4th offense — [Storrito](https://storrito.com/resources/what-tiktoks-ai-monetization-restrictions-signal-for-creator-income/) [secondary]
- **CRP requirements** (secondary sources) — [PostLink](https://postlinkapp.com/blog/tiktok-creator-rewards-program); [Kompozy](https://kompozy.io/creator-growth/tiktok-creator-rewards-program); [TTCalculator](https://ttcalculator.net/learn/creator-fund-countries/); [CreatorsAgency](https://creatorsagency.co/blog/tiktok-creator-rewards-program-2026):
  - France is an eligible country.
  - 10,000 followers, 100,000 views in the last 30 days, age 18+.
  - **Videos must be 60 seconds or longer.**
  - Qualified views come from the For You feed, with at least 5 s watched.
  - Earnings start after 1,000 qualified For You views.

**Copyrighted songs on TikTok**
- **Personal accounts** — [Soundstripe](https://www.soundstripe.com/blogs/tiktok-music-licensing-rules); [Printify](https://printify.com/blog/tiktok-business-account-vs-personal/):
  - Have access to the full Sounds library (label-licensed), licensed for non-commercial posts only.
  - May not use standard-library tracks in any video with paid promotion, a branded-content tag or sponsored material.
- **Business accounts**:
  - See only the Commercial Music Library — [Soundstripe](https://www.soundstripe.com/blogs/tiktok-music-licensing-rules); [Printify](https://printify.com/blog/tiktok-business-account-vs-personal/)
  - May also post music they have licensed themselves, after completing TikTok's "Music Usage Confirmation" at upload — [Soundstripe](https://www.soundstripe.com/blogs/tiktok-music-licensing-rules); [Dynamoi](https://dynamoi.com/learn/tiktok-music-promotion/tiktok-music-licensing)
- TikTok's updated Intellectual Property Policy took effect on 2025-04-26 — [Soundstripe](https://www.soundstripe.com/blogs/tiktok-music-licensing-rules) [OLD >6 mo]
- TikTok's music licenses do not carry over when a video is exported to YouTube. Cross-posting can trigger a Content ID claim or even a strike — [Foxi Music](https://www.foximusic.com/blog/need-background-music-that-wont-trigger-content-id/)

### Inferences
- Practical rules for a French beginner:
  - Never monetize or use in branded content anything made on a free Suno account.
  - On a paid Suno plan, **download each final track within the monthly cap and keep a record** (date, plan, file), because commercial rights now depend on a permitted download.
  - Skip Udio.
  - Keep license proofs (screenshots, Pixabay certificates).
- With Suno, the binding limit for commercial use is downloads, not credits: Pro gives about 500 generations but only 20 usable tracks per month, i.e. about $0.50 per usable track.
- Feeding Suno v6 a copyrighted song as audio or video input could create a derivative-work risk. This is inferred from Suno's "permitted download" rules and the reports of claims for tracks resembling existing songs; it is not stated in any source.
- Micro-stories under 60 s cannot earn CRP payouts whatever the music. Income would have to come from brand deals (which require a business account and CML or self-licensed music), from longer compilations, or from other TikTok programs.
- Stylized wordless AI films with photorealistic AI scenes will probably need the AIGC label. Labeling is a disclosure, not a penalty, but not labeling is penalized.

### Gaps
- Official TikTok wording on AI-generated content in the EEA CRP terms (page blocked). Whether TikTok uses automated audio matching that produces claims on AI music, and how often AI tracks get false claims on TikTok specifically.
- Status in 2026 of the UMG and Sony lawsuits against Suno, and of European actions (GEMA in Germany, Koda in Denmark). Not retrieved.
- Copyright status of AI-generated music under French and EU law (originality requirement). Not researched.
- Whether Suno's 7 free lifetime downloads are personal-use only (very likely, given the terms above, but not stated explicitly).
- Exact current Suno Terms wording on ownership versus license.

---

## Q3. AI sound effects and foley: best tools, how they sync to video, quality and pricing

### Takeaway
For a French creator who wants to monetize, the practical, legally clean choices are:
- **ElevenLabs Sound Effects v2**: up to 30 s, seamless loops, 48 kHz. Good for ambience beds and spot effects.
- **Adobe Firefly Generate Sound Effects**: generally available since 2026-08-20. Takes text or voice imitation, and lets you place sounds against on-screen actions on a timeline.
- **Mirelo**: dedicated video-to-SFX/ambience/music tool, with a Premiere Pro panel and an API.

The strong **open-source video-to-audio models are unsuitable**: MMAudio and ThinkSound are non-commercial, and the HunyuanVideo-Foley license explicitly does not apply in the EU.

### Cited Findings

**ElevenLabs Sound Effects v2**
- Clips up to **30 seconds**, **seamless looping** (extend short effects across longer timeline segments without seams or clicks), **48 kHz** sample rate — [The Decoder](https://the-decoder.com/elevenlabs-releases-version-2-of-its-ai-sound-effects-model-with-longer-clips-and-better-audio-quality/); [Blockchain.news](https://blockchain.news/ainews/elevenlabs-launches-sfx-model-v2-high-quality-ai-sound-effects-with-seamless-looping-and-extended-duration); [Craze](https://www.craze.ai/models/elevenlabs-sound-effects-v2)
- On a third-party API platform, Sound Effects v2 is billed at **$0.003 per second** of generated audio — [Craze](https://www.craze.ai/models/elevenlabs-sound-effects-v2); [JaiPortal](https://www.jaiportal.com/model/elevenlabs-sound-effects-v2); [Layer](https://layer.ai/models/elevenlabs-sound-effects) [secondary; not ElevenLabs' own price list]

**Adobe Firefly (Generate Sound Effects, plus Generate Music)**
- Generate Music, Generate Speech and Generate Sound Effects became generally available in the browser-based Firefly studio on **2026-08-20** — [9to5Mac](https://9to5mac.com/2026/08/20/adobe-fireflys-music-voiceover-and-sound-effects-generation-tools-now-generally-available/)
- Sound effects can be generated from a text prompt or from a **recorded vocal imitation** (voice-to-SFX) — [Adobe HelpX – text-to-SFX](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-audio/text-to-sound-effects.html); [Adobe HelpX – voice-to-SFX](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-audio/voice-to-sound-effects.html)
- When a video is loaded, generated clips **can be placed against specific actions, moved along the timeline, trimmed and volume-adjusted** — [Quasa](https://quasa.io/insights/adobe-firefly-audio-goes-public-but-every-generation-still-uses-credits); [9to5Mac](https://9to5mac.com/2026/08/20/adobe-fireflys-music-voiceover-and-sound-effects-generation-tools-now-generally-available/)
- Firefly can also generate music for an uploaded video — [Adobe HelpX](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-audio/generate-soundtrack-for-an-uploaded-video.html)
- Every generation costs generative credits, so rejected takes and reruns cost money. The Generate button shows the credit cost — [Quasa](https://quasa.io/insights/adobe-firefly-audio-goes-public-but-every-generation-still-uses-credits); [Adobe generative credits overview](https://helpx.adobe.com/firefly/web/get-started/learn-the-basics/generative-credits-overview.html)
- Adobe presents the release as "commercially safe AI audio" — [9to5Mac](https://9to5mac.com/2026/08/20/adobe-fireflys-music-voiceover-and-sound-effects-generation-tools-now-generally-available/)

**Mirelo (dedicated video-to-audio)**
- Analyzes video and generates matching SFX, ambience and music in one click; can batch-generate audio across long timelines — [Tooldirectory](https://tooldirectory.ai/tools/mirelo-ai); [iTechGuides](https://www.itechguides.com/products/mirelo/)
- Integrations: a panel inside Premiere Pro ([Adobe Exchange listing](https://exchange.adobe.com/apps/cc/8a13d073/mirelo-ai)), plus DaVinci Resolve, Roblox Studio and a REST API — [Tooldirectory](https://tooldirectory.ai/tools/mirelo-ai)
- Raised $41M in seed funding in early 2026. **Mirelo SFX 1.6** adds longer generations, extension, seamless loops and inpainting — [Tooldirectory](https://tooldirectory.ai/tools/mirelo-ai); [Mirelo blog – iterative editing](https://www.mirelo.ai/blog/beyond-generation-iterative-editing)
- Also available through an MCP server (Claude, ChatGPT, Cursor) and on Runware — [Mirelo blog – MCP](https://mirelo.ai/blog/introducing-mirelo-mcp); [Mirelo blog – Runware](https://www.mirelo.ai/blog/mirelo-sfx-now-live-on-runware)

**Other generators with SFX**
- Stable Audio 3 **Small SFX**: an open-weight sound-effects model for phones and laptops (2026-05-20) — [MBW](https://www.musicbusinessworldwide.com/stability-ai-launches-new-audio-models-that-can-generate-6-minute-music-tracks/); [MindStudio](https://www.mindstudio.ai/blog/what-is-stable-audio-3-stability-ai)
- Beatoven **Maestro SFX**: the free plan includes 1 Maestro SFX generation per month — [CostBench](https://costbench.com/software/ai-music-apis/beatoven-ai/)

**Open-source video-to-audio models (licenses matter for an EU user)**
- **HunyuanVideo-Foley** (Tencent) — [GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley) [primary, read]; [arXiv paper](https://arxiv.org/html/2508.16930v1):
  - Weights released 2025-08-28; XL model 2025-09-29 [OLD >6 mo].
  - 48 kHz output.
  - VRAM: XXL model 20 GB (12 GB with offload); XL model 16 GB (8 GB with offload).
  - Claims state-of-the-art results against open-source alternatives.
  - **License: Tencent Hunyuan Community License, which "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA"**. The "Territory" is defined as "the worldwide territory, excluding the territory of the European Union, United Kingdom and South Korea". Tencent claims no rights in outputs — [LICENSE](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley/blob/main/LICENSE) [primary, read]
- **MMAudio** — [GitHub](https://github.com/hkchengrex/MMAudio) [primary, read; last update Mar 2025, OLD >6 mo]:
  - Code under MIT; **checkpoints under CC-BY-NC 4.0 (non-commercial)**.
  - Trained on 8-second clips; 44 kHz; about 6 GB of GPU memory.
  - Syncs to video with Synchformer at 25 FPS.
  - Known issues: sometimes produces unintelligible speech-like sounds or unintended background music.
- **ThinkSound / PrismAudio** (FunAudioLLM): Apache 2.0, but "for research and educational purposes only. Commercial use is NOT permitted". PrismAudio was accepted at ICLR 2026 — [GitHub](https://github.com/FunAudioLLM/ThinkSound) [primary, read]
- **FoleyCrafter** (IJCV 2026): video-to-audio framework producing synchronized sound effects — [GitHub](https://github.com/open-mmlab/FoleyCrafter)
- **LTX-2** (Lightricks): released 2026-01-06; generates video and synchronized audio in one pass — [Introl](https://introl.com/blog/ltx-2-audiovisual-diffusion-synchronized-video-audio-2026). The repo now recommends LTX-2.5, with LTX-2.3 kept as legacy — [GitHub](https://github.com/Lightricks/LTX-2) [primary, read; license terms not extracted]

### Inferences
- Recommended stack for a beginner who wants to monetize:
  - ElevenLabs SFX v2 for loopable ambience beds and spot effects.
  - Firefly, if the user already pays for Adobe, for syncing on a timeline and for voice-to-SFX (perform the timing with your voice).
  - Mirelo, if they want automatic foley from a finished cut.
- A France-based user should not use HunyuanVideo-Foley under its community license, because the license does not grant rights in the EU. MMAudio and ThinkSound weights are non-commercial. That leaves no strong open-source video-to-audio model that is legally usable for monetized content in France, apart from possibly Stable Audio 3 Small SFX (text-to-SFX only, license unverified).
- MMAudio's tendency to produce unintended music and speech-like artifacts suggests automatic video-to-audio output generally needs cleaning or replacing before release.

### Gaps
- **Native audio in video generators** (Veo 3.x, Sora 2, Kling 2.6/3.x and its "video-to-audio" feature, Pika, Seedance) was not researched because the search budget ran out. Unverified background knowledge: Veo 3/3.1, Sora 2 and Kling 2.6+ generate synchronized audio. Quality, ability to export without music, and commercial terms are all unverified.
- ElevenLabs SFX v2: official release date, credits per generation in the web app, and free-tier limits.
- Adobe Firefly: plan prices in EUR and credits per SFX or music generation.
- Mirelo: pricing and free tier.
- Independent quality comparisons (creator reviews).

---

## Q4. Free or cheap legal audio sources usable on TikTok, and how business vs personal accounts change things

### Takeaway
For TikTok-only posting, the **Commercial Music Library (CML)** and **CapCut's "commercial" sounds** are free but **locked to TikTok/CapCut**. For audio that is safe on every platform, use:
- **Pixabay** (free, commercial use, no attribution needed, but occasional false Content ID claims)
- **Freesound files under CC0** (avoid CC BY-NC)
- **YouTube Audio Library tracks under CC BY**, with credit
- A paid library: **Epidemic Sound Creator** (about €11/month billed annually) or **Artlist Music & SFX Social** ($9.99/month billed annually)

### Cited Findings
- **CML**: over 1 million pre-cleared, royalty-free tracks and sound effects, free for any TikTok business account — [Soundstripe](https://www.soundstripe.com/blogs/tiktok-music-library-explained); [Dynamoi](https://dynamoi.com/learn/tiktok-music-promotion/tiktok-music-licensing)
- **Business accounts** see only the CML in the in-app editor; the standard Sounds library disappears when you switch to a business account. **Personal accounts** can use both libraries — [Printify](https://printify.com/blog/tiktok-business-account-vs-personal/); [Hootsuite](https://blog.hootsuite.com/tiktok-business-vs-personal/)
- **CapCut Materials License Agreement**: commercial users may show and share videos with "Commercial Sounds" within CapCut, TikTok and TikTok for Business. Any other use needs separate permission from the rights holders — [CapCut license](https://www.capcut.com/clause/material-license-agreement) [primary, via search summary]
- CapCut's "commercial use" label means cleared only inside TikTok/CapCut. Such tracks may trigger claims on YouTube or Instagram or in monetized content. Licenses attach to each element of the video, not to the finished MP4 — [Artyfile](https://artyfile.com/blog/capcut-music-commercial-use-guide); [Foxi Music](https://www.foximusic.com/royalty-free-music-licensing-for-capcut-videos/); [CapCutGuide](https://capcutguide.com/capcut-commercial-use-rights/)
- **Pixabay** — [Pixabay FAQ](https://pixabay.com/service/faq/); [Pixabay blog – clearing Content ID claims](https://pixabay.com/blog/posts/how-to-clear-a-youtube-content-id-claim-with-a-pix-190/); [StackInfluence](https://stackinfluence.com/blog/find-royalty-free-commercial-music-for-tiktok); [Foxi Music](https://www.foximusic.com/blog/need-background-music-that-wont-trigger-content-id/):
  - Its Content License allows commercial use with no attribution; 170,000+ free tracks.
  - Some contributors or their distributors register tracks in Content ID, which can produce automated claims even on legal uses.
  - Pixabay's license certificate is accepted as proof when disputing a YouTube claim.
- **Freesound**: the license is set per file by the uploader — [ScribeCount](https://scribecount.com/author-resource/tricks-of-the-trade/free-royalty-free-sound-music-authors); [Cinevva](https://app.cinevva.com/guides/free-sound-effects-music)
  - **CC0**: public domain, no credit needed.
  - **CC BY**: commercial use allowed with credit.
  - **CC BY-NC**: no commercial use.
  - Filtering on CC0 avoids attribution questions.
- **YouTube Audio Library**: tracks carry either the "YouTube Audio Library License" (no attribution) or CC BY 4.0 (attribution required). Secondary sources say standard-license tracks may only be used in YouTube videos, while CC BY tracks can be used elsewhere, including TikTok, with credit — [vidIQ](https://vidiq.com/ru/blog/post/how-to-best-free-music-youtube-royalty-free); [SocialPilot](https://www.socialpilot.co/youtube-marketing/youtube-audio-library) [secondary; Google's own help page could not be read]
- **Epidemic Sound**: renamed its plans in 2025 (Personal and Commercial became **Creator** and **Pro**); EUR prices in Q6 — [Photutorial](https://photutorial.com/epidemic-sound-pricing/); [OMR](https://omr.com/en/reviews/product/epidemic-sound/pricing)
- **Artlist**: Music & SFX Social, Music & SFX Pro and Max plans; prices in Q6. New annual customers get 2 extra months — [Photutorial](https://photutorial.com/artlist-pricing/); [CC Hound](https://www.cchound.com/artlist/artlist-subscription-plans-and-pricing/); [Artlist blog](https://artlist.io/blog/artlist-pricing-and-plans-explained/)

### Inferences
- **Personal account** (most likely for a beginner): the full TikTok Sounds library is technically allowed for organic, non-sponsored posts. However, that music cannot follow the video to YouTube Shorts or Reels, and becomes off-limits once a video is sponsored.
- **Business account**: CML only, plus self-licensed music such as AI tracks from a paid plan, Pixabay, Freesound CC0, or Epidemic/Artlist.
- Building each video's soundtrack outside TikTok (paid AI generator plus Pixabay or CC0 SFX) and importing it as original audio gives a cleaner rights trail and allows cross-posting.

### Gaps
- Official TikTok CML documentation could not be read: whether CML tracks may be reused in videos cross-posted elsewhere (secondary sources say TikTok-only), and whether some CML tracks are AI-generated.
- Whether Epidemic Sound or Artlist subscriptions need a channel "whitelist" for TikTok, and how their licenses treat TikTok business accounts.
- Whether the EUR prices above include French VAT (20%).

---

## Q5. Practical sound design for wordless storytelling (layering, silence, music cues, mobile loudness)

### Takeaway
**I could not gather sourced expert or community guidance** (r/aivideo, YouTube filmmakers, loudness specs for TikTok) before the search budget ran out. What is sourced is the set of **tool features that make a layered workflow possible**:
- Loopable ambience (ElevenLabs SFX v2, Mirelo 1.6)
- Action-synced SFX placement (Firefly, Mirelo)
- Music whose ending or climax can be rewritten (Suno v6 section edits, ElevenLabs v2 inpainting, Flow Music Replace/Extend)
- Exact length control (ACE-Step 1.5, Lyria 3.5)
- Stems to make room in the mix (Suno Premier Studio, Flow Music stem splitting)

Craft advice below is general practice, explicitly flagged as unverified.

### Cited Findings
- **Ambience beds**: ElevenLabs SFX v2 loops extend short effects across longer timeline segments without seams or clicks — [Craze](https://www.craze.ai/models/elevenlabs-sound-effects-v2); [The Decoder](https://the-decoder.com/elevenlabs-releases-version-2-of-its-ai-sound-effects-model-with-longer-clips-and-better-audio-quality/). Mirelo SFX 1.6 adds seamless loops, extension and inpainting — [Tooldirectory](https://tooldirectory.ai/tools/mirelo-ai)
- **Spot SFX synced to actions**: Firefly lets you place generated clips against specific on-screen actions and trim or adjust their volume — [Quasa](https://quasa.io/insights/adobe-firefly-audio-goes-public-but-every-generation-still-uses-credits). Voice-to-SFX lets you perform a sound's timing and shape with your voice — [Adobe HelpX](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-audio/voice-to-sound-effects.html). Mirelo generates ambience and SFX automatically from the video — [Tooldirectory](https://tooldirectory.ai/tools/mirelo-ai)
- Mirelo has published a guide on adding AI sound effects without masking dialogue (only the title was retrieved) — [Mirelo blog](https://mirelo.ai/blog/ai-sound-effects-keep-dialogue)
- **Emotional arc and endings in the music**:
  - Suno v6 can change one section while leaving the rest intact — [PicLumen](https://www.piclumen.com/blog/suno-v6-review/)
  - ElevenLabs v2 offers section inpainting and genre transitions (a mid-track mood change) — [ElevenLabs blog](https://elevenlabs.io/blog/introducing-music-v2)
  - Flow Music offers Replace and Extend — [Creative AI News](https://www.creativeainews.com/blog/google-flow-music-launch-lyria-3-ai-studio/)
  - Beatoven Maestro is marketed for "more nuanced emotional transitions" — [Tooliverse](https://tooliverse.ai/tools/beatoven-ai)
- **Exact duration to match the edit**:
  - ACE-Step 1.5 duration, BPM and time-signature metadata — [GitHub](https://github.com/ace-step/ACE-Step-1.5)
  - Lyria 3.5 tempo and duration control — [MLQ](https://mlq.ai/news/google-releases-lyria-35-in-flow-music-with-upgraded-vocals-and-song-controls/)
  - Stable Audio 3 variable length — [MBW](https://www.musicbusinessworldwide.com/stability-ai-launches-new-audio-models-that-can-generate-6-minute-music-tracks/)
- **Stems for mixing space**: Suno Premier exports 32-bit/48 kHz stems from Studio — [SiliconSense](https://siliconsense.club/guides/suno-v6). Flow Music has stem splitting — [MBW](https://www.musicbusinessworldwide.com/googles-flow-music-adds-song-generation-editing-and-stem-splitting-to-spaces-its-vibe-coding-tool/)
- **Automatic video-to-audio needs cleanup**: MMAudio may add unintended music or speech-like sounds — [GitHub MMAudio](https://github.com/hkchengrex/MMAudio)
- Video-to-music tools that "score" a clip directly: Lyria 3 in Gemini (upload a video), Firefly "Generate music for videos", Suno v6 (video input) — [9to5Google](https://9to5google.com/2026/02/18/gemini-app-music-lyria-3/); [Adobe HelpX](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-audio/generate-soundtrack-for-an-uploaded-video.html); [Suno on X](https://x.com/suno/status/2097846245540888664)

### Inferences
- A beginner workflow that follows from the tool features above:
  1. Lock the picture edit first.
  2. Lay a looped **ambience bed** (ElevenLabs SFX v2 or Mirelo).
  3. Add **spot SFX/foley** on key actions (Firefly timeline or Mirelo).
  4. Generate a **score** at the exact length, or regenerate only the ending so the musical resolution lands on the final shot (Suno v6 section edit, ElevenLabs inpainting, Flow Music Replace/Extend, ACE-Step duration).
  5. Use stems to thin out the music where an SFX or a silence must carry the moment.
- Because many viewers watch TikTok with sound off or on phone speakers, both the visual and the audio storytelling must work on their own. This is an inference from the format, not sourced.

### Gaps
- **No sourced loudness target for TikTok.** Unverified background practice: streaming platforms are often mixed to about −14 LUFS integrated with true peak at or below −1 dBTP. Phone speakers reproduce little below about 100–150 Hz, so emotional cues that rely on sub-bass may disappear. Both points need verification.
- No sourced recommendations from experienced AI filmmakers. Unverified craft conventions:
  - A short silence or a sudden drop just before the emotional peak increases impact.
  - Room tone or ambience should never fully cut out (total digital silence sounds like an error).
  - A recurring motif (a few piano notes) gives a series an identity.
  - The music should follow the story beats (setup, turn, release) rather than loop evenly.
- No data on how TikTok's audio compression affects AI-generated music, or on best export settings (AAC bitrate, sample rate).

---

## Q6. Pricing tables (as of October 2026; USD unless noted)

### Takeaway
A **€0 legal kit** is possible:
- CML or CapCut for TikTok-only use
- Pixabay and Freesound CC0
- Flow Music / Lyria 3.5 (free, but commercial terms unverified)
- ACE-Step locally (MIT; needs a GPU)

A **beginner paid kit at about $15–16/month** is:
- **Suno Pro** ($10/month: 20 commercially usable downloads/month)
- **ElevenLabs Starter** ($5–6/month: commercial SFX v2 and Eleven Music)

**Epidemic Sound Creator** (€10.99/month billed annually) or **Artlist Music & SFX Social** ($9.99/month billed annually) is a cheap stock-library alternative or complement.

### Cited Findings

**AI music generators**

| Tool (version) | Free tier | Paid plans (per month) | Commercial use | Source |
|---|---|---|---|---|
| **Suno** (v6 / v6-wild / v6-mini, since 2026-09-09) | Yes (v6-mini implied); **non-commercial**; 7 lifetime downloads (since 2026-09-03) | **Pro $10**: 2,500 credits (~500 songs at ~5 credits/song), **20 downloads/month**, v6 + v6-wild. **Premier $30**: 10,000 credits (~2,000 songs), **60 downloads/month**, Studio multitrack/stem export (32-bit/48 kHz) without using a download. Extra downloads can be bought (price unknown) | Only for songs downloaded while subscribed, within the cap | [roo.beehiiv](https://roo.beehiiv.com/p/suno-v6-features); [Layer3 Labs](https://www.layer3labs.io/guides/suno-pricing); [TechJack](https://techjacksolutions.com/ai-tools/suno/suno-pricing/); [MuseGen](https://www.musegen.ai/blog/suno-download-limits-what-changed-alternatives); [HookGenius](https://hookgenius.app/learn/suno-free-vs-pro-comparison/) |
| **Udio** | Plans exist; prices not retrieved | n/a | **No downloads since 2025-10-30** | [Undetectr](https://undetectr.com/blog/udio-download) |
| **ElevenLabs** (Eleven Music v2, May 2026; credits shared across all ElevenLabs products) | Free plan exists (not commercial for music; implied) | **Starter $6** (another source says **$5**), Creator $22, Pro $99, Scale $299, Business $990. Music API about **$0.15/min** (as reported, after the May 2026 price cut) | Starter and above; self-serve excludes film/TV/studio games | [Gradually.ai](https://www.gradually.ai/en/elevenlabs-pricing/); [BigVU](https://bigvu.tv/blog/elevenlabs-pricing-2026-plan-worth/); [ElevenLabs API pricing](https://elevenlabs.io/pricing/api); [Glad-IA-tor](https://glad-ia-tor.com/tool/eleven-labs-music) |
| **Google Flow Music** (Lyria 3.5, 2026-07-29) | **Lyria 3.5 free for all Flow Music users** | Paid tiers not verified | Not verified | [TUN](https://www.tun.com/home/google-deepmind-launches-lyria-3-5-in-flow-music-ai-music/); [AI Creators Tools](https://aicreators.tools/voice-audio/music-generators/riffusion) |
| **Gemini app** (Lyria 3, 30 s clips) | "Rolling out … for all" (beta) | Subscription details not verified | Not verified | [9to5Google](https://9to5google.com/2026/02/18/gemini-app-music-lyria-3/) |
| **Lyria 3 Pro API** (Gemini API / AI Studio / Vertex) | n/a | **$0.08 per song** (preview, Aug 2026), any length up to 3 min | API terms (not retrieved) | [OpenRouter](https://openrouter.ai/google/lyria-3-pro-preview); [BenchLM](https://benchlm.ai/media-pricing/lyria) |
| **Mureka** (V8 Jan 2026; V9.5 Aug 2026) | Not retrieved | **Pro $10** (or $8/month billed yearly): 5,000 "Gold" (~500 songs), unlimited MP3, full commercial rights. *Conflicting report*: Pro $9 / **Premier $27** (WAV, stems, MIDI, Studio, voice cloning). API: V8 generate **$0.07/generation**, extend $0.15 | Pro and above | [Gaga.art](https://gaga.art/blog/mureka-v8/); [Future Stack Reviews](https://future-stack-reviews.com/mureka-ai-review/); [WaveSpeed](https://wavespeed.ai/collections/mureka-ai) |
| **Soundraw** | Not retrieved | Creator **$11.04** (unlimited MP3; videos, ads, client work); Artist Starter $19.49 (10 songs, MP3); Artist Pro $23.39 (20 songs, WAV + stems); Artist Unlimited $32.49. *Other sources report $16.99–$50* | Yes; tracks made while subscribed stay licensed for life | [CostBench](https://costbench.com/software/ai-music-generators/soundraw/); [Toolradar](https://toolradar.com/tools/soundraw/pricing) |
| **AIVA** | Not retrieved | **Standard €11** (billed annually; some sources say $11): AIVA keeps copyright, monetization allowed on YouTube/Twitch/**TikTok**/Instagram, 15 downloads/month, tracks up to 5 min, MP3 + MIDI. **Pro €33** (billed annually): you own the copyright | Standard: platform-limited; Pro: unrestricted | [CostBench](https://costbench.com/software/ai-music-generators/aiva/); [Tooliverse](https://tooliverse.ai/tools/aiva); [CostBench AIVA vs Soundraw](https://costbench.com/compare/aiva-vs-soundraw/) |
| **Beatoven.ai** (Maestro) | 1 Composer generation + 1 Maestro music generation + 1 Maestro SFX generation per month | **Creator $10** (or $100/year): unlimited generations, 30 min of downloads. **Visionary $20** (or $200/year): 60 min of downloads. Pay-as-you-go **$3 per downloaded minute** | Paid plans: "exclusive music license" | [CostBench](https://costbench.com/software/ai-music-apis/beatoven-ai/); [Toolradar](https://toolradar.com/tools/beatoven/pricing) |
| **ACE-Step 1.5** (XL 2026-04-02) | **Free, MIT license**, runs locally (≥6 GB VRAM; 12 GB+ for XL) | n/a | Yes (disclose AI involvement) | [GitHub](https://github.com/ace-step/ACE-Step-1.5) |
| **YuE2** (Sept 2026) | **Free**; 24 GB VRAM locally, or free online demo | n/a | Individual creators may monetize; companies need a license | [GitHub](https://github.com/multimodal-art-projection/YuE) |
| **MusicGen** (AudioCraft) | Free | n/a | **No** (weights CC-BY-NC) | [GitHub](https://github.com/facebookresearch/audiocraft) |
| **Stable Audio 3** (2026-05-20) | Open weights (Small SFX, Small, Medium) | API and enterprise prices not retrieved | Open-weight license not verified | [MBW](https://www.musicbusinessworldwide.com/stability-ai-launches-new-audio-models-that-can-generate-6-minute-music-tracks/) |

**SFX tools**

| Tool | Price | Source |
|---|---|---|
| ElevenLabs Sound Effects v2 | Included in ElevenLabs plans (see above); **$0.003/s** of generated audio through a third-party API | [Craze](https://www.craze.ai/models/elevenlabs-sound-effects-v2) |
| Adobe Firefly Generate Sound Effects / Music | Metered by generative credits per generation (plan prices not retrieved) | [Quasa](https://quasa.io/insights/adobe-firefly-audio-goes-public-but-every-generation-still-uses-credits); [Adobe credits overview](https://helpx.adobe.com/firefly/web/get-started/learn-the-basics/generative-credits-overview.html) |
| Mirelo | Not retrieved | [iTechGuides](https://www.itechguides.com/products/mirelo/) |

**Stock and free libraries**

| Source | Price | Notes | Source |
|---|---|---|---|
| TikTok Commercial Music Library | Free (business accounts) | 1M+ tracks and SFX; TikTok-only | [Soundstripe](https://www.soundstripe.com/blogs/tiktok-music-library-explained) |
| CapCut "Commercial Sounds" | Free | Licensed only within CapCut, TikTok and TikTok for Business | [CapCut license](https://www.capcut.com/clause/material-license-agreement) |
| Pixabay Music/SFX | Free | Commercial use, no attribution; occasional false Content ID claims | [Pixabay FAQ](https://pixabay.com/service/faq/) |
| Freesound | Free | Per-file CC0 / CC BY / CC BY-NC | [ScribeCount](https://scribecount.com/author-resource/tricks-of-the-trade/free-royalty-free-sound-music-authors) |
| YouTube Audio Library | Free | Standard license reportedly YouTube-only; CC BY tracks usable elsewhere with credit | [vidIQ](https://vidiq.com/ru/blog/post/how-to-best-free-music-youtube-royalty-free) |
| **Epidemic Sound Creator** | **€17.99 monthly** or **€10.99/month billed yearly (€131.88/year)** | Plan renamed from "Personal" in 2025 | [Photutorial](https://photutorial.com/epidemic-sound-pricing/); [OMR](https://omr.com/en/reviews/product/epidemic-sound/pricing) |
| **Epidemic Sound Pro** | **€39.99 monthly** or **€16.99/month billed yearly (€203.88/year)** | Commercial plan | same |
| **Artlist Music & SFX Social** | **$14.99 monthly** or **$9.99/month billed annually ($119.88/year)** | | [Photutorial](https://photutorial.com/artlist-pricing/); [CC Hound](https://www.cchound.com/artlist/artlist-subscription-plans-and-pricing/) |
| Artlist Music & SFX Pro | $24.92/month (annual only, $299.04/year) | | same |
| Artlist Max | $39.99/month billed annually ($479.88/year) | Music, stems, SFX, footage, AI tools | same |

### Inferences
- **Effective cost per commercially usable track**:
  - Suno Pro: $10 / 20 downloads ≈ **$0.50**; Premier: $30 / 60 ≈ **$0.50**.
  - Lyria 3 Pro API: **$0.08**.
  - Mureka API: **$0.07** per generation.
  - Beatoven pay-as-you-go: a 30-second cue ≈ **$1.50**.
  - ElevenLabs SFX v2 API: a 10-second effect ≈ **$0.03**.
- **Suggested budget tiers for a French beginner** (prices before possible VAT):
  1. **€0**: Flow Music / Gemini Lyria (check terms) + Pixabay + Freesound CC0 + CML/CapCut for TikTok-only posts.
  2. **About €15/month**: Suno Pro + ElevenLabs Starter.
  3. **About €25–45/month**: add Epidemic Creator (annual) or upgrade to Suno Premier for stems.

### Gaps
- Official EUR prices for Suno, ElevenLabs, Mureka, Soundraw, Beatoven and Artlist, and whether they include VAT.
- Annual-billing discounts for Suno.
- Free-tier details for AIVA, Soundraw and Mureka.
- Udio's current plan prices.
- Pricing for Mubert, Loudly, Soundful, MusicGPT, Flow Music, Stable Audio (consumer site), Adobe Firefly and Mirelo.
- Several prices come only from aggregators that disagree with each other (Soundraw, Mureka, ElevenLabs Starter at $5 vs $6). They should be checked on official pages before publication.
