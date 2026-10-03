# AI image generators, character/style consistency techniques, and all-in-one AI creative platforms (state as of 3 Oct 2026, for a French beginner making wordless TikTok micro-stories with a recurring character)

> **Read this first (how the research was done).** Research date: 2026-10-03. The sandbox's network proxy blocked every direct page fetch (official pricing pages, Midjourney docs, Trustpilot, TechCrunch, Wikipedia, etc.), and the session-wide web-search budget ran out after ~45 queries. **All findings below therefore come from search-engine result summaries.** For each claim I cite the result page(s) the summary most likely drew on; where a summary blended several results, I cite the 1–2 most plausible. **No number below could be double-checked on a live official page.** Treat prices as "reported by [source]" and re-check them before publishing. Many sources are SEO or affiliate blogs, or blogs run by competing vendors (Higgsfield, Krea, Luma, Magnific, Invideo and Mage all publish pages about each other's pricing). I flag that bias where it matters. Any finding dated before ~April 2026 is flagged as possibly outdated.

---

## 1. Which image generators are best right now (Oct 2026) for consistent characters and cinematic keyframes?

### Takeaway
For keeping the same character across many keyframes, the leaders in Sept–Oct 2026 are two families of models: **Google's Nano Banana** (Nano Banana Pro gives the tightest identity control; Nano Banana 2 is faster/cheaper and takes up to 14 reference images) and **OpenAI's GPT Image 2 / 2.5** (sold as "ChatGPT Images"), which can produce up to 8 coherent images of the same character from one prompt. **Midjourney V8.x** is still the aesthetic leader for stylized looks. However, in July–Aug 2026 it replaced Character Reference and Omni Reference with a new "Edit Model" that takes up to 4 references, and its consistency tools draw community criticism. Strong alternatives, mostly reached through aggregators, are **FLUX.2**, **Seedream 5.0** and **Ideogram Character** (free, works from one photo).

### Cited Findings

#### Google: Nano Banana family (Gemini image models)
- **Nano Banana 2 = Gemini 3.1 Flash Image.** Announced 26 Feb 2026 — [TechCrunch, 2026-02-26](https://techcrunch.com/2026/02/26/google-launches-nano-banana-2-model-with-faster-image-generation/). Google marketed it as "Pro-level quality, at Flash speed", rolling out across the Gemini app, Search and its developer and creative tools — [Google on X](https://x.com/Google/status/2027051657163391104?lang=en); [Google blog](https://blog.google/innovation-and-ai/technology/ai/nano-banana-2/).
- Gemini 3.1 Flash Image reportedly reached general availability (GA) on 28 May 2026 — [Google Cloud docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-1-flash-image).
- A cheaper, faster **"Nano Banana 2 Lite"** was introduced on 30 June 2026 — [TechCrunch, 2026-06-30](https://techcrunch.com/2026/06/30/google-introduces-a-faster-cheaper-image-generator-with-nano-banana-2-lite/) (headline only).
- **Nano Banana Pro** keeps consistency and resemblance for **up to 5 people** across generations. It keeps an edge in character consistency and in following complex instructions. **Nano Banana 2 supports up to 14 reference images** to keep subjects, styles and characters consistent — [fal.ai](https://fal.ai/learn/tools/nano-banana-pro-vs-nano-banana-2); [Magnific blog](https://www.magnific.com/blog/nano-banana-2-vs-nano-banana-pro/); [Melies](https://melies.co/compare/nano-banana-2-vs-nano-banana-pro).
- Comparison verdict:
  - **Nano Banana 2** suits rapid character and object variations.
  - **Nano Banana Pro** suits shots where identity, pose, clothing, scene placement and narrative continuity must stay tightly controlled.
  - Some hands-on tests found Nano Banana 2 excelled on speed, photorealism and character consistency.
  - Sources: [AIToolsSME (4-prompt test)](https://www.aitoolssme.com/blogs/nano-banana-pro-vs-nano-banana-2); [Banani](https://www.banani.co/blog/nano-banana-pro-vs-nano-banana-2).
- **Gemini app limits** (status as of 28 Mar 2026, **older than 6 months, may have changed**):
  - The app generates with Nano Banana 2 by default. Nano Banana Pro is offered mainly as a "Redo with Pro" option.
  - Daily Redo caps: **50/day on Google AI Plus, 100/day on Google AI Pro, 1,000/day on Google AI Ultra**.
  - Free users get only about **2–4 Nano Banana Pro images/day** before falling back to the standard model.
  - Sources: [AIFreeAPI – restrictions](https://www.aifreeapi.com/en/posts/nano-banana-pro-restrictions); [AIFreeAPI – rate limits](https://www.aifreeapi.com/en/posts/nano-banana-pro-rate-limits); [AIFreeAPI – is it free](https://www.aifreeapi.com/en/posts/nano-banana-pro-free).
- A practitioner guide calls Nano Banana "the leading tool for character sheets". It produces 360° turnaround sheets at 4K: four angles plus face and mid-angle close-ups — [Invideo blog](https://invideo.io/blog/ai-filmmaking-tools/). Invideo is a vendor that resells these models.

#### OpenAI: GPT Image 2 / 2.5 ("ChatGPT Images")
- **Release:** gpt-image-2 launched in the API and Codex on **21 Apr 2026**. It reached consumers as **"ChatGPT Images 2.0" on 22 Apr 2026** on every ChatGPT plan. It succeeds GPT Image 1.5 and is OpenAI's first image model with native reasoning ("thinking") — [OpenAI](https://openai.com/index/introducing-chatgpt-images-2-0/); [MindStudio](https://www.mindstudio.ai/blog/what-is-gpt-image-2).
- **Capabilities:** it can generate **up to eight coherent images from a single prompt, keeping characters and objects consistent across the set**. Aspect ratios run from 3:1 to 1:3, resolution "up to 2K" — [MindStudio](https://www.mindstudio.ai/blog/what-is-gpt-image-2); [BuildFastWithAI](https://www.buildfastwithai.com/blogs/chatgpt-images-2-0-gpt-image-2-2026).
  - **Conflicting claim:** marketing from a reseller says "native 4K", "99% text accuracy" and 3–5× faster — [Picsart](https://picsart.com/ai-models/gpt-2/).
- **Two modes:**
  - "Instant" mode is available to all ChatGPT users, including free.
  - "Thinking" mode (web search, layout reasoning, multi-image batching, output verification) is restricted to **Plus ($20/mo)**, Pro ($200/mo), Business and Enterprise.
  - Source: [BuildFastWithAI](https://www.buildfastwithai.com/blogs/chatgpt-images-2-0-gpt-image-2-2026).
- **GPT Image 2.5 / "ChatGPT Images 2.5"** was released in ChatGPT on **8 Sep 2026**. It adds a "Sketch" feature (turns a drawing into an image) and cuts latency by about 50% — [Wikipedia: GPT Image](https://en.wikipedia.org/wiki/GPT_Image). Dreamina also advertises a "GPT Image 2.5 deal" — [Dreamina summer sale](https://dreamina.capcut.com/resource/dreamina-summer-sale-2026).
- As of Sept 2026, "GPT Image 2.5 variants and Google's Nano Banana 2 both rank near the top for reference-guided editing" — [Tech-Insider 5-model consistency test](https://tech-insider.org/consistent-ai-character-generator-test-2026/); [Fast.io](https://fast.io/resources/best-ai-character-generators-2026/).

#### Midjourney: V8.x
- **V8.1** became the default model (announced on Midjourney's updates site; exact date not retrieved). A third-party article titled "Midjourney May 2026 Update: V8.1, Pricing & Video" suggests around May 2026 — [Midjourney updates](https://updates.midjourney.com/v8-1-is-now-the-default-model/); [PixVerse](https://pixverse.ai/en/blog/midjourney-ai-image-generator-review); [Creativity AI #79](https://geekycuriosity.substack.com/p/creativity-ai-79-midjourney-makes).
- **V8.2** became the default on **24 Jul 2026**. It focuses on aesthetics, image quality and Personalization. Its new **Edit Model replaces Omni Reference, Character Reference and the Retexture tool** on the V8 family — [Midjourney docs: Version](https://docs.midjourney.com/hc/en-us/articles/32199405667853-Version); [Blake Crosley guide](https://blakecrosley.com/guides/midjourney).
- **The Edit Model** was opened to everyone (public testing) on **27 Aug 2026**. What it does:
  - edits an image from written instructions;
  - blends **up to 4 image references**;
  - repaints or extends specific areas;
  - works with personalization, moodboards, style references, image prompts and `--hd`.
  - Omni Reference's old job (consistent output from a reference image) now happens through this multi-image reference flow.
  - Sources: [Miraflow](https://miraflow.ai/blog/midjourney-v8-2-edit-model-guide-prompts-2026); [AlphaSignal](https://alphasignal.ai/news/midjourney-s-v8-2-edit-model-merges-inpainting-references-and-instructions-into); [Powerdrill](https://powerdrill.ai/blog/midjourney-v8-2-edit-model).
- Midjourney's own feature chart marks **Character Reference and Character Weight as unsupported on V8.1 and V8.2** — [Clipdance](https://clipdance.ai/blog/midjourney-v8-character-consistency). Omni Reference (`--oref`) is a **V7** feature — [Midjourney docs: Omni Reference](https://docs.midjourney.com/hc/en-us/articles/36285124473997-Omni-Reference).
- **Community criticism:** an AI creator on X (about Apr 2026) called Midjourney's Omni Reference "beyond terrible, it's unusable" for character consistency and doubted it would work with V8 — [@FussyPastor on X](https://x.com/FussyPastor/status/2044597655180054755).
  - **Contrasting view:** a 2026 roundup says "Midjourney with Omni Reference produces the highest-quality consistent characters in 2026" (paid plans from $10/mo) — [Fast.io](https://fast.io/resources/best-ai-character-generators-2026/). This likely predates the V8.2 changes.
- **Pricing (USD).** Annual billing is 20% cheaper: $8 / $24 / $48 / $96 per month. Sources: [Costbench](https://costbench.com/software/ai-image-generators/midjourney/); [Fluxnote](https://fluxnote.io/guides/midjourney-pricing-guide-2026); [UXMagic](https://uxmagic.ai/blog/midjourney-pricing).

| Plan | Monthly price | What it includes |
|---|---|---|
| Basic | $10 | ~200 min Fast GPU time, no Relax mode |
| Standard | $30 | 15 h Fast + unlimited Relax images |
| Pro | $60 | 30 h Fast, Relax, stealth mode, Relax SD video |
| Mega | $120 | 60 h Fast |

#### Black Forest Labs: FLUX
- **FLUX.2.** The Pro model has 32 billion parameters and was released in **Nov 2025** (older than 6 months). It adds:
  - multi-reference conditioning (character, layout and style across **up to 10 reference images**);
  - 4 MP output;
  - sharper text;
  - hex-colour steering.
  - Sources: [MindStudio](https://www.mindstudio.ai/blog/what-is-flux-2-pro); [Fluxnote](https://fluxnote.io/guides/flux-2).
- FLUX.2 Pro via API costs about **$0.03 per 1024×1024 image**, with 6–9 s latency and up to 8 input images — [MindStudio](https://www.mindstudio.ai/blog/what-is-flux-2-pro).
- **FLUX.2 [klein]** (4B/9B compact models, open weights) was released in Jan 2026 — [MarkTechPost, 2026-01-16](https://www.marktechpost.com/2026/01/16/black-forest-labs-releases-flux-2-klein-compact-flow-models-for-interactive-visual-intelligence/).
- **Unverified (reseller blog only):** "FLUX 3", a multimodal image/video/audio model, reportedly launched 23 Jul 2026 with video in early access — [Kie.ai](https://kie.ai/blog/what-is-flux-3).
- One review headline calls FLUX 2 "The 2026 Photorealism Leader" — [The Planet Tools](https://theplanettools.ai/tools/flux-2).
- The previous FLUX.1 Kontext line (2025) was an image-editing line — [Wikipedia: Flux](https://en.wikipedia.org/wiki/Flux_(text-to-image_model)).
- A German integrator publishes a page on "FLUX versions, benchmarks & EU availability" (content not retrieved) — [innFactory](https://innfactory.ai/en/ai-models/flux/).

#### ByteDance: Seedream 5.0
- **Seedream 5.0 Lite** was released in **Feb 2026** (text-to-image, optional reference images) — [MindStudio](https://www.mindstudio.ai/models/seedream-v5-0-lite).
- **Seedream 5.0 Pro** was released on **8 Jul 2026**. It generates and edits images and is described as a "reasoning" model — [OpenArt blog](https://openart.ai/blog/seedream-5-0-pro-overview/); [Promptslove](https://promptslove.com/blog/seedream-5-pro-the-complete-guide/).
- Claimed breakthroughs: complex information visualization, interactive precision editing, photorealism, native multilingual support — [BigGo Finance](https://finance.biggo.com/news/970b9042-b2b4-4d0e-aee0-e926785d936f).
- API prices: **Pro $0.075/image** (up to 2.36 MP), **Lite $0.035/image** — [Promptslove](https://promptslove.com/blog/seedream-5-pro-the-complete-guide/).
- Seedream 5.0 Pro is unlimited (marked as a promo) on Magnific Premium+ — [AutoKeyWorder](https://autokeyworder.com/blog/magnific-pricing/).

#### Ideogram: Ideogram Character
- Builds a consistent character from **one reference photo**, with no training, dataset or LoRA.
- It is **free on ideogram.ai and the iOS app**. Ideogram's page says no subscription is needed for creative projects, freelance designs or personal use. Plus and Pro add "unlimited character generations", private images and more credits — [Ideogram](https://ideogram.ai/features/character/).
- In one test it was "the only free-tier tool that kept facial features locked across all five test images" — [Fast.io](https://fast.io/resources/best-ai-character-generators-2026/).
- Paid plans are reported at **Plus $20/mo** and **Pro $60/mo** — [SaaSworthy](https://www.saasworthy.com/product/ideogram-ai/pricing); [AIGearBase](https://aigearbase.com/tool/ideogram).

#### Platform-native image models and character features
- **Leonardo's own models:** Lucid Origin, Lucid Realism, Phoenix 1.0/0.9 (unlimited at relaxed speed on the Premium plan), plus "Motion" video models — [TechSifted](https://techsifted.com/guides/leonardo-ai-pricing-2026/).
- **Krea's own models:** "Krea 2" plus real-time models — [Costbench](https://costbench.com/software/ai-image-generators/krea/); [AIPhotoLabs](https://aiphotolabs.com/reviews/krea-ai-review-2025-real-time-creative-suite-with-multi-model-power/).
- **Mage.space "Characters":** upload one portrait, name it, reuse it with `@charactername` — [Mage blog](https://blog.mage.space/article/best-ai-image-generators-consistent-characters-2026/392f47f0-6619-4021-9b07-ba3ed8c86ba8) (vendor's own claim).
- **ToonyStory** (children's storybook tool) claims photo-based character locking across 20+ illustrated pages and says it beat general tools on multi-page consistency — [ToonyStory](https://toonystory.com/blog/best-ai-for-character-consistency-2026) (vendor's own test of "7 generators on 140 images"; details not retrieved).

### Inferences
- **Default stack for a recurring stylized character in Oct 2026:**
  1. Design the character and build a character sheet in Nano Banana Pro (or ChatGPT Images 2.x).
  2. Generate every shot's keyframe by editing from that sheet.
- **GPT Image 2's "8 coherent images per prompt"** (Thinking mode, paid ChatGPT) works as a built-in storyboard generator for a 6–8 shot micro-story.
- **Midjourney** is still the best pick for a distinctive art direction (personalization, moodboards, style references). But Character Reference and Omni Reference are gone on V8.x, and the Edit Model handles at most 4 references, so a beginner should not rely on Midjourney alone to lock identity. A sensible hybrid: set the look in Midjourney, then do identity and pose edits in Nano Banana or GPT Image.
- **Access route:** beginners will usually reach FLUX.2, Seedream 5.0, Nano Banana and GPT Image through aggregators (Magnific, Krea, OpenArt, Firefly, Artlist and others) rather than directly.

### Gaps
- **No 2026 data retrieved on Reve, Recraft or Qwen-Image-Edit** (search budget exhausted). Unverified background, not to be cited: Qwen-Image-Edit 2509/2511 (open weights, Alibaba) supported multi-image editing in late 2025; Reve and Recraft V3 were 2025 models. Newer versions may exist.
- **No sourced comparison by style** (anime, Pixar-like 3D, watercolor, claymation). No independent quantitative consistency benchmark was retrieved; the vendor tests above (ToonyStory, Tech-Insider) were seen only as snippets.
- **Midjourney details missing:** the exact V8.1 default date, the initial V8 release date, any newer Midjourney video model, and commercial-use terms.
- **Nano Banana free limits** in the Gemini app after March 2026, and in France specifically, are not confirmed.

---

## 2. Character and style consistency techniques (image → video): which approach do practitioners recommend for beginners?

### Takeaway
Practitioners in 2026 converge on a **reference-first pipeline**:
1. Lock a multi-angle **character sheet** (front, side, back and ¾ views, plus face close-ups) using an image-editing model.
2. Generate **each shot's keyframe from that sheet**.
3. Animate each keyframe, either with **image-to-video** (start frame, optionally an end frame) or with the video tool's own reference system:
   - Kling 3.0 Elements
   - Veo 3.1 Ingredients
   - Seedance 2.0 multi-reference
   - Runway Gen-4.5 references
   - Sora character cameos (animals and objects only)

Training a **LoRA** is now optional and advanced; guides say character sheets can replace it.

### Cited Findings

#### Character sheets / turnarounds
- **Recommended sheet:** four turnaround angles (front, side, back, ¾) plus face and mid-angle close-ups, at the highest resolution available; documented productions used 4-angle sheets at 4K. Close-up panels are "not optional", because small details (scars, accessories) drift across video models — [Invideo blog](https://invideo.io/blog/ai-filmmaking-tools/); [Invideo FAQ](https://invideo.io/faq/how-do-you-use-a-character-reference-sheet-to-keep-ai/).
- "A consistency error caught at the image stage costs one regeneration; the same error caught at the video stage costs a re-shoot of every clip that inherited it." — [Invideo blog](https://invideo.io/blog/ai-filmmaking-tools/).
- The same guide says character sheets "replace LoRA fine-tuning entirely". It cites one 70-second short film that kept two characters consistent across every scene using sheets and agent context alone — [Invideo blog](https://invideo.io/blog/ai-filmmaking-tools/). Invideo is a vendor.
- Pairing character sheets with storyboards is pitched as "one simple trick" for cinematic AI video — [SeeB4Coding](https://blog.seeb4coding.in/create-cinematic-ai-videos-with-one-simple-trick-character-sheets-storyboards/) (headline only).
- A 2026 article compares five img2img consistency methods — [Flick.art](https://flick.art/blog/img2img-consistent-character) (content not retrieved).

#### Reference systems inside video tools
- **Kling 3.0 "Elements" (subject binding)**
  - Upload 2–4 reference images of the character (front, side, back, detail), name it, and tag it as `@Name` in prompts.
  - The Elements 3.0 asset library can also take reference video clips of up to 8 s and bind a voice profile.
  - Without Elements, "by shot 3 you'd have character drift" (face shape, hair, clothing).
  - Sources: [Kling blog](https://kling.ai/blog/kling-3-subject-binding-character-consistency); [Medium (2-week Kling 3.0 test)](https://medium.com/@info.booststash/i-spent-two-weeks-pushing-kling-3-0-to-its-limits-heres-everything-nobody-is-telling-you-411cc0d49f51); [Atlas Cloud](https://www.atlascloud.ai/blog/guides/how-to-use-kling-3.0-for-character-consistency); [Flick.art](https://flick.art/blog/kling-character-consistency).
  - "Kling 3.0 Omni" also does reference-to-video — [Kling 3.0 Omni guide](https://kling.ai/quickstart/klingai-video-3-omni-model-user-guide).
- **Veo 3.1 "Ingredients to Video"** (Google Flow)
  - Up to **3 reference images** (character, object, scene or style), plus a prompt explaining how they interact.
  - Reusing the same ingredients across clips keeps character, location and object consistent.
  - It is the alternative to Flow's first/last-frame mode.
  - Sources: [Technave](https://technave.com/gadget/How-to-get-consistent-characters-with-Google-Veo-3-and-Flow-43421.html); [Atlas Cloud](https://www.atlascloud.ai/blog/guides/how-to-use-veo-3-1-ingredients-to-video-transforming-static-photos-into-cinematic-ai-clips); [Google Cloud – Veo 3.1 prompting guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1).
- **Seedance 2.0** (ByteDance)
  - Accepts up to **12 assets per generation**: up to 9 images, 3 video clips and 3 audio clips, plus text.
  - Outputs multi-shot video with native audio and supports several referenced characters in one scene.
  - Sources: [MindStudio](https://www.mindstudio.ai/blog/what-is-seedance-2-video-model); [Atlas Cloud](https://www.atlascloud.ai/blog/case-studies/generative-ai-model-seedance-2-0-a-guide-to-all-round-reference); [Resident, 2026-09-11](https://resident.com/technology-and-digital-resources/2026/09/11/how-seedance-20-transforms-visual-references-into-connected-cinematic-scenes-in-2026).
  - Invideo calls Seedance 2.0 reference-to-video "the strongest current tool" for consistent shots from a character sheet — [Invideo FAQ](https://invideo.io/faq/what-is-the-best-ai-tool-for-generating-consistent-video/). Invideo resells Seedance, so this is biased.
- **Runway Gen-4.5**
  - Clips of 2–10 s. One reference image keeps face, clothing and colours — [Krea model page](https://www.krea.ai/models/runway).
  - Recommended route: make a sharp reference image in a separate image tool, upload it as the identity anchor, then prompt the action, camera, mood and duration (image-to-video). This "separates character design from motion generation" — [UD.hk guide, 2026-05-05](https://www.ud.hk/en/blogs/insight/article/2026-05-05-runway-gen4-guide).
  - Aleph extends this to in-context editing and multi-shot work — [Morphic](https://morphic.com/resources/models/runway-gen4-aleph).
  - **Unverified:** a vendor blog claims the AI Video Arena ranks Gen-4.5 image-to-video first on character consistency — [Mage](https://blog.mage.space/article/best-ai-video-generators-consistent-characters-2026/9459a229-806d-4a73-8abf-a19db645a248).
- **Sora 2 "character cameos"** (late 2025, **older than 6 months**)
  - Any user can upload a short video of a pet or object to create a reusable, taggable character with its own permissions (private, followers, or everyone).
  - OpenAI: "Character cameos are for objects and animals only. They're not for real people."
  - Sources: [eWeek](https://www.eweek.com/news/openai-sora-character-cameos/); [The Outpost](https://theoutpost.ai/news-story/open-ai-s-sora-introduces-character-cameo-feature-turning-pets-and-objects-into-ai-video-stars-21347/); [BGR](https://www.bgr.com/2011808/sora-character-cameos-invite-free-access-new-markets/).

#### Start-frame / end-frame chaining
- Flow offers a first/last-frame mode (image as the first or last frame) as the alternative to Ingredients — [Technave](https://technave.com/gadget/How-to-get-consistent-characters-with-Google-Veo-3-and-Flow-43421.html).
- Runway's recommended workflow is image-to-video from a still made in another tool — [UD.hk](https://www.ud.hk/en/blogs/insight/article/2026-05-05-runway-gen4-guide).

#### LoRA / custom training
- **Krea Max ($105/mo)** includes unlimited LoRA training — [Costbench](https://costbench.com/software/ai-image-generators/krea/).
- **LTX Studio "trained actors":** up to 8/month on Lite, unlimited on Standard — [Omid Saffari](https://omidsaffari.com/blog/ltx-studio-pricing); [Vidmuse](https://vidmuse.ai/blog/ltx-studio-review).
- Invideo's guide says character sheets "replace LoRA fine-tuning entirely" — [Invideo blog](https://invideo.io/blog/ai-filmmaking-tools/).

#### Storyboarding tools with consistency features
- **LTX Studio:** writes scenes, visuals and storyboards from a script. AI-generated storyboards require the Standard plan ($35/mo); free users can still build storyboards by hand — [The Rundown](https://www.therundown.ai/tools/ltx-studio); [Vidmuse](https://vidmuse.ai/blog/ltx-studio-review).
- **OpenArt "One-Click Story":** turns a prompt or outline into a sequence of illustrated panels or scenes without re-prompting each one — [Affmaven](https://affmaven.com/openart-pricing/); [AIBlogFirst](https://aiblogfirst.com/openart-ai-storyboard-generator/).
- **GPT Image 2 Thinking mode:** up to 8 consistent images per prompt — [MindStudio](https://www.mindstudio.ai/blog/what-is-gpt-image-2).
- **Adobe Firefly Boards:** unlimited on all Firefly plans — [Photutorial](https://photutorial.com/adobe-firefly-price/); [The Rundown](https://www.therundown.ai/tools/adobe-firefly).
- **Node canvases** for repeatable multi-model pipelines: Flora (50+ models), Figma Weave, Krea Nodes / Nodes Agent — [Wireflow](https://www.wireflow.ai/blog/flora-ai-pricing); [UXMagic](https://uxmagic.ai/blog/figma-weave-review); [Costbench](https://costbench.com/software/ai-image-generators/krea/).
- **Midjourney:** moodboards, style references and personalization work together with the V8.2 Edit Model, which helps keep a consistent "world" or style — [Miraflow](https://miraflow.ai/blog/midjourney-v8-2-edit-model-guide-prompts-2026).

### Inferences (beginner workflow distilled from the sources above)
1. **Write a 4–8 shot beat sheet.** With no dialogue, emotion has to come from expression, posture, framing, light, colour and music.
2. **Design the character once.** Use Nano Banana Pro or ChatGPT Images for identity; Midjourney if you want a strong art style. Then make a turnaround sheet plus face close-ups. Also save a small "style bible": palette, lighting and lens words, and 1–2 style-reference images.
3. **Make every keyframe by editing from the sheet** and the style reference, never from a blank prompt. Fix drift at this image stage, where it is cheap.
4. **Animate each approved keyframe:**
   - image-to-video from the start frame;
   - add an end frame for controlled moves or transitions;
   - or attach the same sheet through the video model's reference system (Kling Elements, Veo Ingredients, Seedance references), reusing the same named element or ingredient in every shot.
5. **Keep clips short (5–8 s) and cut between them.** Drift grows with clip length.
6. **Skip LoRA training** unless producing at volume or with a very specific house style.
- **What wordless stories don't need:** lip-sync, which is the hardest consistency problem. So voice binding (Kling Elements) and talking-avatar platforms (Hedra) are unnecessary spending.
- **Animal or object protagonists** (a cat, a robot, a toy): Sora's character cameos are an extra consistency route. They are explicitly not for real people.

### Gaps
- No 2026 data retrieved on Vidu reference-to-video (Q2/Q3), Hailuo, Wan or Luma references, and no sourced 2026 best-practice guide for start/end-frame chaining.
- **No community sources (Reddit, YouTube channels such as Theoretically Media, Curious Refuge, Tao Prompts) were retrieved** before the search budget ran out. The "consensus" above rests on vendor and creator blogs.
- Not confirmed: whether Sora character cameos accept stylized fictional humans, and whether Sora is available in the EU.

---

## 3. All-in-one platforms, aggregators and AI filmmaking suites: models, storytelling features, prices, credit burn, "unlimited" fine print, commercial rights, complaints

### Takeaway
- **Higgsfield:** biggest marketing presence, but the worst reputation. Trustpilot is about 3.2/5; users report billing, refund and "unlimited"-throttling complaints; and it has faced several 2025–26 marketing scandals.
- **Magnific (the Freepik AI suite, renamed Apr 2026):** has the most concretely specified "unlimited" offer — Nano Banana 2 and Kling 2.5 at 720p, for €25.50/mo on annual billing.
- **Krea and OpenArt:** solid mid-priced creative suites. OpenArt has explicit character slots and One-Click Story.
- **Big-brand bundles:** Google AI Pro (Nano Banana Pro plus Flow/Veo), Adobe Firefly (30+ partner models plus Boards) and ChatGPT Plus (GPT Image 2.x).
- **General rule:** credits almost never roll over, and "unlimited" almost always means specific older or lower-resolution models, relaxed or queued speed, or undisclosed fair-use caps.

### Cited Findings

#### Overview table
Figures are reported prices in USD per month on monthly billing unless noted; sources are in the per-platform bullets below.

| Platform | Entry → mid paid tiers | Allowance | Key models (reported) | Story / consistency features | "Unlimited" fine print | Watch-outs |
|---|---|---|---|---|---|---|
| Higgsfield | Conflicting ladders: $9 / $29 / $79 **or** $19 / $59 / $129 | 120–3,000 credits | Seedance 2.0 and other hosted models | Popcorn, Cinema Studio, Soul ID (details not retrieved) | Metered; "battery" throttling | Trustpilot ~3.2/5; refunds; scandals |
| Magnific (ex-Freepik) | Premium $20 ($14.50 annual); Premium+ $45 ($33.75 annual; **€25.50 annual**) | 240K / 600K credits per year | NB2, Kling 2.5 / 3.0, Veo 3.1, Seedream 5.0 Pro, Hailuo 2.3 | Spaces (not retrieved) | Premium+: NB2, Kling 2.5 720p/5 s, Seedream 5 Pro (promo), Hailuo 2.3 Fast | Free tier = personal use + attribution |
| Krea | Basic $9; Pro $35; Max $105 | 5K / 20K / 60K compute units | Krea 2, NB2, Runway Gen-4.5, "all video models" on Pro | Nodes, Nodes Agent, App Builder, LoRA training | Max: unlimited relaxed generations + LoRA | Max price conflict ($70 vs $105) |
| OpenArt | Starter $14; Plus $34; Pro $56 (−50% annual) | 4K / 12K / 24K credits | Seedream 5.0 Pro and others | 13 / 40 / 80 character slots; 5 / 17 / 34 One-Click Stories | — | Prices rose in 2026 |
| LTX Studio | Lite $15; Standard $35 | Free plan: 800 one-time credits | Not retrieved | Script → storyboard; trained actors | — | Commercial use only from $35 |
| Leonardo | Essential $12; Premium $30; Ultimate $60 | 8.5K / 25K / 60K fast tokens | Lucid, Phoenix, FLUX Dev/Schnell, Motion | Not retrieved | Premium: relaxed select image models; Ultimate: relaxed Motion video | Free generations are public |
| Google AI Pro (Flow) | $19.99 | 1,000 AI credits; NB Pro redo 100/day | Veo 3.1, NB2 / NB Pro | Ingredients; first/last frame | — | EUR price not retrieved |
| Adobe Firefly | Standard $9.99; Pro $19.99 | 2,000 / ~4,000 credits | 30+ partner models (NB2, Veo 3.1, Runway Gen-4.5, Kling 2.5 Turbo, FLUX, Ideogram, ElevenLabs…) | Firefly Boards (unlimited) | — | — |
| Dreamina (ByteDance / CapCut) | $18; $82 | 1,575 / 8,645 credits + free daily credits | Seedance 2.0 / 2.5, GPT Image 2.5 (deal) | Not retrieved | Time-limited promos | Free-credit figures conflict |
| Artlist AI | Starter $19.99; Core $39.99; Creator $69.99 | 16.5K / 40K / 80K credits | 38 video models (Seedance 2.0, Veo 3.1, Kling 3.0, Sora 2, Wan 2.7, Grok Imagine…), Nano Banana | Image + video + voice + music on one credit pool | "Select models" unlimited | — |
| Invideo AI | Plus ≈$28 monthly / $17 annual-equivalent | 750 credits (period unclear) | Veo 3.1, Kling 3.0, Seedance 2.0 | Agent-based editing | — | Credits forfeited each cycle |
| Pollo AI | Lite $15; Pro $29 | 400 / 800 credits | Pollo 2.5, Seedance 2.5, Veo, Sora, Kling | — | — | No rollover |
| ImagineArt | Basic $9; Standard $30; Ultimate $50 | 2K / 8K / 16K credits | ImagineArt models | — | Ultimate/Creator "unlimited" with undisclosed limits | — |
| Kaiber Superstudio | Creator $29 ($23.25 annual) | 1,400 credits | Not retrieved | Canvases | Visionary (custom) = unlimited | $5 trial auto-converts to paid |
| Hedra | Basic $15; Creator $30 | 1,500 / 5,400 credits | Character-3 | Talking avatars / lip-sync | — | Poor fit for wordless videos |
| Flora | Starter $18/seat; Pro $50/seat | Usage budget = plan price | 50+ models | Node canvas | — | Aug 2026 launch pricing is time-limited |
| Figma Weave (ex-Weavy) | Starter $19; Professional $36 (annual) | 1,500 / 4,000 credits | Google, OpenAI, Runway, Luma, ByteDance, BFL, Kling | Node canvas | Professional: 3-month credit rollover | — |
| Canva | Pro **€110/yr** | 50 shared AI credits/mo | Veo 3 (8-s clips with audio) | Magic Studio | — | Very small video allowance |

#### Higgsfield
- **Plans (conflicting reports; the pricing changed several times in 2026):**
  - The consumer plan names Basic / Pro / Ultimate / Creator were reportedly retired for **Starter / Plus / Ultra / Business** between Jan and Apr 2026 — [Camclo3d](https://camclo3d.com/blog/higgsfield-pricing); [UsagePricing](https://www.usagepricing.com/blueprint/higgsfield).
  - **Ladder A:** Basic $9/mo (120 credits); Pro $29/mo or $23 annual (600 credits); Max $79/mo or $59 annual (1,800 credits) — [Luma](https://lumalabs.ai/news/higgsfield-pricing); [Krea blog](https://www.krea.ai/blog/what-is-higgsfield-ai-pricing-free-plan-and-alternatives-in-2026). Both are competitors' pages.
  - **Ladder B:** Starter $19/mo (270 credits); Plus $59 monthly or $47 annual (1,200 credits); Ultra $129 monthly or $99 annual (3,000 credits) — [Camclo3d](https://camclo3d.com/blog/higgsfield-pricing); [AIForesight360](https://aiforesight360.com/higgsfield-ai-pricing/).
- **Fine print:**
  - "Unlimited" plans are metered in practice. Users report throttling at peak times and a **"battery" system** that can lock them out of unlimited mode until they pay for extra access.
  - Unlimited-mode jobs are queued while credit-based jobs run instantly.
  - Credits do not roll over; top-up packs expire after about 90 days.
  - Sources: [GStory](https://www.gstory.ai/blog/higgsfield-ai/); [Pixmax](https://www.pixmax.ai/blog/higgsfield-ai-review.html).
- **Reviews:**
  - Trustpilot is around **3.2/5 across about 3,700 reviews**. Negative reviews cluster around refunds denied, surprise charges after cancellation and high credit consumption — [Pixmax](https://www.pixmax.ai/blog/higgsfield-ai-review.html); [GStory](https://www.gstory.ai/blog/higgsfield-ai/).
  - Example reviews: a "7 days unlimited" offer on Plus/Pro sent the buyer to upgrade to the Max plan to actually use unlimited. Another user lost a full **$384 annual plan** after cancelling on day 9 under a 7-day cancellation policy — [Trustpilot CA, p.2](https://ca.trustpilot.com/review/higgsfield.ai?page=2); [Trustpilot NZ, p.6](https://nz.trustpilot.com/review/higgsfield.ai?page=6).
  - Reddit users documented **2–6× price increases within three months** — [GStory](https://www.gstory.ai/blog/higgsfield-ai/); [Pixmax](https://www.pixmax.ai/blog/higgsfield-ai-review.html).
- **Marketing and ethics controversies:**
  - Reported **$300M ARR in 11 months**, alongside fierce creator backlash over racist AI-generated promo content (Shrek characters using anti-Asian slurs, a Moana character delivering racist dialogue), non-consensual celebrity deepfakes (Sydney Sweeney, Zendaya), and offers to pay creators to share deliberately offensive clips — [WebProNews](https://www.webpronews.com/higgsfields-300-million-rocket-ride-how-an-ai-video-startups-meteoric-growth-unleashed-a-firestorm-of-creator-backlash-and-ethical-reckoning/); [ProductGrowth](https://www.productgrowth.blog/p/higgsfield-growth-teardown); [Quasa](https://quasa.io/media/how-higgsfield-ai-became-shitsfield-ai-a-cautionary-tale-of-overzealous-growth-hacking).
  - **Creator/affiliate programme:** claimed a 90% approval rate, but creators reported withdrawal problems, sudden account bans and unpaid work. One influencer said undisclosed paid promotion broke FTC guidelines and X's paid-amplification policy. There was also an "X ban" episode — [Caimera](https://www.caimera.ai/blogs/higgsfield-ai-twitter-ban-case-study-how-platform-trust-collapses); [AIPhotoLabs](https://aiphotolabs.com/news/higgsfieldai-x-fiasco). The dates of the X episode were not retrieved.
  - **Aug 2026:** YouTubers Matti Haapoja and Sam "Kold" Kolder were criticized for sudden Higgsfield promos. Other creators shared screenshots of partnership offers from PR firms linked to Higgsfield — [Dataconomy, 2026-08-21](https://dataconomy.com/2026/08/21/youtube-creators-face-backlash-over-ai-partnership-with/); [The News](https://www.thenews.com.pk/latest/1413111-ai-filmmakers-are-under-fire-over-their-sudden-higgsfield-promotions-heres-why).
  - Kazakh press headline: "Scam claims and backlash hit Kazakhstan's AI unicorn Higgsfield" — [Qazinform](https://qazinform.com/news/scam-claims-and-backlash-hit-kazakhstans-ai-unicorn-higgsfield-b311a7).
  - A separate headline reports a "$1B revenue run rate" — [Design Musketeer](https://designmusketeer.com/business/higgsfield-ai-1b-annualized-revenue/) (headline only).
- **SEO footprint:** Higgsfield hosts Seedance 2.0 — [Higgsfield](https://higgsfield.ai/seedance/2.0) — and publishes many comparison posts ranking itself, such as "Best All-in-One Subscription for AI Images and Video" and "8 Best Unlimited AI Video Generators" — [Higgsfield blog](https://higgsfield.ai/blog/best-all-in-one-subscription-ai-images-video); [Higgsfield blog](https://higgsfield.ai/blog/best-unlimited-ai-video-generators).

#### Magnific (formerly the Freepik AI suite)
- **Rebrand:** Freepik renamed its AI platform **Magnific on 28 Apr 2026**. Freepik had bought Magnific in May 2024. The old standalone upscaler plans were folded into one credit-based subscription covering upscaling plus image, video and audio generation from a shared balance — [Oakgen](https://oakgen.ai/blog/magnific-ai-freepik-rebrand-pricing); [Vantaige](https://vantaige.io/blog/freepik-ai-is-now-magnific-pricing-changes-2026); [Wikipedia: Magnific](https://en.wikipedia.org/wiki/Magnific).
- **Plans (USD).** Sources: [Oakgen](https://oakgen.ai/blog/magnific-ai-freepik-rebrand-pricing); [Vibedex](https://vibedex.ai/blog/freepik-ai-review-2026); [CheckThat](https://checkthat.ai/brands/freepik/pricing).

| Plan | Monthly | Annual (per month) | Credits | Notes |
|---|---|---|---|---|
| Free | $0 | — | — | Up to 20 AI images/day (in-house model), 10 stock downloads/day; personal use only, attribution required |
| Premium | $20 | $14.50 | 240K/year | — |
| Premium+ | $45 | $33.75 | 600K/year | Plus unlimited use of ~10 image models |
| Pro | $280 | $210 | 4M/year | — |
| Business | — | $55/seat (annual only, minimum 2 seats) | 1.08M shared | — |

- **EUR price:** Premium+ is **€25.50/mo on annual billing** — [AutoKeyWorder](https://autokeyworder.com/blog/magnific-pricing/); [Magnific pricing](https://www.magnific.com/pricing). This is inconsistent with the $33.75 USD figure; verify on checkout.
- **What Premium+ makes unlimited:** Nano Banana 2, **Kling 2.5 (720p, 5 s clips)**, Seedream 5.0 Pro (promo tag) and Hailuo 2.3 Fast. Newer or higher-resolution video models (e.g., Kling 3.0, Veo 3.1 4K) cost credits on every plan — [AutoKeyWorder](https://autokeyworder.com/blog/magnific-pricing/); [Eesel](https://www.eesel.ai/blog/freepik-ai-pricing).
- **Credit burn:** **Veo 3.1 in 4K with audio costs 2,080 credits per 4-second clip** — [MyArchitectAI](https://www.myarchitectai.com/blog/magnific-ai-pricing); [Promptsrush](https://promptsrush.com/blog/magnific-pricing).
- Magnific's own blog claims "The strongest AI deal is on Magnific" — [Magnific blog](https://www.magnific.com/blog/strongest-ai-deal/) (vendor claim).
- **Conflict:** one page lists "Magnific AI Pricing 2026: $16, $37 & $90 Plans", probably the legacy upscaler plans — [RenderAHouse](https://www.renderahouse.com/blog/magnific-ai-pricing).

#### Krea
- **Plans.** Sources: [Costbench](https://costbench.com/software/ai-image-generators/krea/); [Comparedge](https://comparedge.com/tools/krea-ai/pricing).

| Plan | Price/mo | Compute units | Includes |
|---|---|---|---|
| Free | $0 | 100/day | Krea 2, real-time models, limited image and video models |
| Basic | $9 | 5,000 | All image models, selected video models, **commercial license** |
| Pro | $35 | 20,000 | All video models, App Builder, Nodes Agent |
| Max | $105 | 60,000 | Unlimited LoRA training, unlimited relaxed generations, more concurrency |
| Business | $200 | 80,000 | Up to 50 seats |

- **Conflict:** a Costbench headline lists Max at **$70** — [Costbench](https://costbench.com/software/ai-image-generators/krea/).
- **Burn:** Pro's 20,000 units ≈ **257 Nano Banana 2 images, about $0.14 each** on monthly billing — [Costbench](https://costbench.com/software/ai-image-generators/krea/).
- Krea hosts Runway Gen-4.5 — [Krea model page](https://www.krea.ai/models/runway).
- Krea also publishes competitor pages, e.g., about Higgsfield and Firefly pricing — [Krea blog](https://www.krea.ai/blog/what-is-higgsfield-ai-pricing-free-plan-and-alternatives-in-2026).

#### OpenArt
- **Plans:** Starter **$14/mo** (4,000 credits), Plus **$34** (12,000), Pro **$56** (24,000), Wonder **$240** (106,000). Annual billing halves the price (from $7/mo) — [Affmaven](https://affmaven.com/openart-pricing/); [Affinco](https://affinco.com/openart-pricing/).
- **Consistent-character slots:** 13 / 40 / 80 / 353. **One-Click Stories:** 5 / 17 / 34 / 150 by plan — [Affmaven](https://affmaven.com/openart-pricing/).
- Hosts Seedream 5.0 Pro — [OpenArt blog](https://openart.ai/blog/seedream-5-0-pro-overview/).
- **Complaint:** a review headline says "Prices Rose. Is It Still Worth It?" — [AIReiter](https://aireiter.com/blog/openart-ai-review-2026-pricing).

#### LTX Studio
- **Plans:** Free (800 one-time credits); Lite **$15/mo or $12 annual**; Standard **$35 or $28 annual**; Pro **$125 or $100 annual**; Enterprise custom — [AIToolsAtlas](https://aitoolsatlas.ai/tools/ltx-studio/pricing); [Vidmuse](https://vidmuse.ai/blog/ltx-studio-review).
- **Commercial use starts at Standard ($35)** — [Omid Saffari](https://omidsaffari.com/blog/ltx-studio-pricing).
- Script → scenes → storyboard workflow; trained actors up to 8/month on Lite, unlimited on Standard; AI-generated storyboards need Standard — [The Rundown](https://www.therundown.ai/tools/ltx-studio); [Omid Saffari](https://omidsaffari.com/blog/ltx-studio-pricing).

#### Leonardo
- **Plans.** Team plans: Starter $24/seat, Growth $48/seat. Sources: [TechSifted](https://techsifted.com/guides/leonardo-ai-pricing-2026/); [Omid Saffari](https://omidsaffari.com/blog/leonardo-ai-review).

| Plan | Price/mo | Fast tokens | Notes |
|---|---|---|---|
| Free | $0 | 150/day | Generations are public; non-exclusive commercial license |
| Essential | $12 | 8,500/mo (bank up to 25,500) | Private generations |
| Premium | $30 | 25,000/mo (bank up to 75,000) | Unlimited relaxed: Lucid Origin, Lucid Realism, Phoenix, FLUX Dev/Schnell |
| Ultimate | $60 | 60,000/mo | Unlimited relaxed video on Motion models |

#### Google AI plans / Flow
- **Google AI Pro: $19.99/mo**, including **1,000 AI credits** for Flow. Credits are Google's compute currency for Flow, Antigravity and agent tasks: roughly 200/month on Plus, 1,000 on Pro, and 10,000–25,000 on Ultra — [Digital Applied](https://www.digitalapplied.com/blog/google-ai-plans-free-plus-pro-ultra-2026); [SaaSCRMReview](https://saascrmreview.com/google-flow-pricing/).
- Google's subscription page is titled "Google AI Pro & Ultra — get access to Gemini 3.1 Pro & more" — [Google](https://gemini.google/subscriptions/).
- The Pro plan also gives 100 Nano Banana Pro "redos" per day in the Gemini app (status as of Mar 2026) — [AIFreeAPI](https://www.aifreeapi.com/en/posts/nano-banana-pro-rate-limits).
- Flow features: Veo 3.1 Ingredients to Video (up to 3 references) and first/last-frame mode — [Technave](https://technave.com/gadget/How-to-get-consistent-characters-with-Google-Veo-3-and-Flow-43421.html).
- An October 2026 page on Flow costs exists but could not be read — [CostGoat](https://costgoat.com/pricing/google-flow).

#### Adobe Firefly
- **Plans (as of Sept 2026):** Standard **$9.99/mo** (2,000 generative credits, video generation, audio translation); Pro **$19.99** (about double the credits; one aggregator says it also adds Photoshop and Express access, which is unverified); Pro Plus ≈ $49.99; Premium **$199.99** (50,000 credits) — [Photutorial](https://photutorial.com/adobe-firefly-price/); [AIProductivity](https://aiproductivity.ai/pricing/adobe-firefly/).
- **Partner models:** 30+, including Google Nano Banana 2 and Veo 3.1, Runway Gen-4.5, Kling 2.5 Turbo, FLUX, Ideogram, Topaz and ElevenLabs, all under one subscription. **Firefly Boards is unlimited on all plans** — [The Rundown](https://www.therundown.ai/tools/adobe-firefly); [Krea blog](https://www.krea.ai/blog/is-adobe-firefly-free-what-it-is-and-how-it-compares-in-2026).

#### Dreamina (ByteDance / CapCut)
- **Subscriptions:** $18/mo (1,575 credits) and $82/mo (8,645 credits) — [PriceMyAI](https://pricemyai.com/pricing/dreamina/).
- **Free credits (conflicting):** about 60–120 bonus credits/day per one source, a "daily allotment of 225 free credits" per another — [PriceMyAI](https://pricemyai.com/pricing/dreamina/).
- **Per-clip cost:** about **$1.29 per standard 720p 8-second clip ($1.06 on Fast)**, described as the lowest among the platforms compared — [PriceMyAI](https://pricemyai.com/pricing/dreamina/).
- **Promotion running 23 Sep – 9 Oct 2026:** 90% off the first month. Seedance 2.5 from **$0.035/second at 720p**; US introductory payment $1.50. Under the Basic first-month offer, Seedance 2.0 Fast/Mini cost $0.008/s and Seedance 2.0 Pro $0.016/s (720p) — [Dreamina – Seedance 2.5 pricing](https://dreamina.capcut.com/seedance/seedance-2-5-pricing-2026); [Dreamina – Seedance 2.0 pricing](https://dreamina.capcut.com/seedance/seedance-2-0-pricing); [Atlas Cloud](https://www.atlascloud.ai/blog/tips/seedance-2.5-pricing-guide).
- Headline: "Seedance 2.0 Is Now Global: Best Platforms, Pricing, and Content Restrictions Explained" — [MindStudio](https://www.mindstudio.ai/blog/seedance-2-global-release-platforms-restrictions).

#### Artlist AI
- **Plans:** AI Starter **$19.99/mo** (16,500 credits), AI Core **$39.99** (40,000), AI Creator **$69.99** (80,000). Annual billing is about 40% cheaper.
- **Custom Business plan:** unlimited generation on all models, custom business license, **legal indemnification**.
- **Models:** 38 video models, including Seedance 2.0, Veo 3.1, Kling 3.0 (full Kling family), Grok Imagine, Wan 2.7, Sora 2 and "Happy Horse 1.0"; image generation via Wan 2.7 Pro and ImagineArt 2.0; 100+ models in total, including Nano Banana.
- **Credits** are shared across image, video, voiceover and music; select models are unlimited without using credits.
- Sources: [AIToolsSME](https://www.aitoolssme.com/review/artlist-video); [WhichAITool](https://www.whichaitool.com/details/artlist-video); [Vuela](https://vuela.ai/alternative/artlist/pricing); [SelectHub](https://www.selecthub.com/p/ai-video-generator-software/artlist/).

#### Invideo AI
- **Plans:** Plus $17/mo ($200/yr, 750 credits); Max $85 ($1,000/yr, 3,900 credits); Generative $170 ($2,000/yr, 8,000 credits); Elite $900 ($10,800/yr, 42,500 credits). The free plan is watermarked — [Creatify](https://creatify.ai/blog/invideo-pricing-(2026)-plans-credits-and-what-you-ll-actually-pay); [Valmera](https://valmera.io/blog/invideo-review).
- Costbench gives **$28–$899/month** on monthly billing — [Costbench](https://costbench.com/software/ai-video-generators/invideo-ai/). It is unclear whether the credit figures above are monthly or yearly.
- **Burn per second of video:** Veo 3.1 at 720p/1080p without audio **0.8 credits/s**; Kling 3.0 at 720p without audio about **0.67 credits/s**; Seedance 2.0 at 720p about **0.73 credits/s** — [Creatify](https://creatify.ai/blog/invideo-pricing-(2026)-plans-credits-and-what-you-ll-actually-pay).
- Unused credits and iStock allowances are forfeited each cycle — same source.

#### Pollo AI
- **Plans:** Free (20 credits, 1 parallel task); Lite **$15/mo or $12 annual** (400 credits, no watermark); Pro **$29 or $14.50 annual** as a "flash sale" (800 credits); Ultra **$129 or $99 annual** (5,000 credits).
- **Burn:** a 5 s clip costs 5 credits on Pollo 2.5 (720p) but **30 credits on Seedance 2.5 (480p)**.
- Plan credits don't roll over; add-on credits never expire but aren't refundable.
- Models include Veo, Sora, Kling and Seedance.
- Sources: [Toolstacker](https://toolstacker.io/pollo-ai-pricing); [AIReviewLab](https://aireviewlab.io/pollo-ai-pricing/).

#### ImagineArt
- **Plans:** Basic **$9/mo** (2,000 credits), Standard **$30** (8,000), Ultimate **$50** (16,000), Creator **$250** (100,000), Enterprise custom; free plan gives 100 credits/day.
- Ultimate and Creator offer "unlimited generations on key models", but the **"unlimited" limits are not disclosed**. Credits don't roll over.
- Sources: [ImagineArt help](https://help.imagine.art/subscription-plans-and-pricing); [CompareBestAI](https://comparebestai.com/articles/imagineart-pricing); [Flowith](https://flowith.io/blog/imagine-art-pricing-2026-free-credits-vs-pro/).

#### Kaiber Superstudio
- **Plans:** Flex $0 (pay-as-you-go, 3 concurrent generations, 2 canvases); Creator **$29/mo or $23.25 annual** (1,400 credits); Pro **$149** (7,500 credits, 20% off credit packs); Visionary custom (unlimited).
- **Credit packs:** 300 for $5, 1,000 for $15, 3,500 for $50, 20,000 for $250.
- **Trial:** $5 for 5 days (300 credits), which **auto-converts to a Creator monthly subscription**.
- Sources: [Kaiber help center](https://helpcenter.kaiber.ai/en/articles/10001319-understanding-subscriptions-and-pricing); [VideoIA.fr](https://videoia.fr/en/kaiber-ai-review/). The help-centre article date was not visible.

#### Hedra
- **Plans:** Basic **$15/mo** (1,500 credits), Creator **$30** (5,400), Professional/Teams **$75** (14,400); free plan 100 credits.
- **Burn:** Character-3 costs **6 credits per second**, so a 60 s video costs 360 credits.
- Monthly credits expire; purchased packs don't.
- Sources: [AIYogeum (Sep 2026)](https://aiyogeum.com/en/tools/hedra); [Fluxnote](https://fluxnote.io/guides/hedra-ai-review); [Magic Hour](https://magichour.ai/blog/guide-to-hedra-ai).

#### Flora (flora.ai)
- **Plans:** Starter **$18/seat/mo**, Pro **$50**, Max **$200**, Enterprise custom. The **August 2026 launch pricing is explicitly time-limited**.
- The free plan gives 3 projects, text and image models only, and about 17 generations in total (lifetime). Video models start at Starter.
- The paid price equals the same dollar amount of usage budget per seat, charged at per-model rates (from under 1 cent to several dollars per generation).
- 50+ models on a node canvas.
- Sources: [Wireflow](https://www.wireflow.ai/blog/flora-ai-pricing); [The Rundown](https://www.therundown.ai/tools/flora-ai).

#### Figma Weave (formerly Weavy)
- **Background:** Weavy was founded in Tel Aviv in 2024 and acquired by Figma in Oct 2025.
- **Plans:** Free (150 credits/mo); Starter **$19/mo** (1,500 credits ≈ 3,750 images or 417 s of video); Professional **$36** (4,000 credits, 3-month rollover); Team $48/user, annual billing.
- **Models:** from Google, OpenAI, Runway, Luma, ByteDance, BFL and Kling.
- Sources: [UXMagic](https://uxmagic.ai/blog/figma-weave-review); [Luma](https://lumalabs.ai/news/weave-pricing); [Overs](https://www.overs.studio/guides/what-is-figma-weave).

#### Canva AI
- **Price:** Canva Pro is **€110/year** for one person on Canva's euro pricing page (checked 29 Sep 2026) — [Grafista](https://grafista.io/blog/posts/canva-pro).
- **Video limits (as of June 2026):** the free plan gets 5 video credits in total; Pro gets 50 shared AI credits/month across Magic Studio; generated clips max out at 4 s — [Fluxnote](https://fluxnote.io/guides/canva-ai-video-generator-review).
- Another source lists "Canva AI Video" (Veo 3, 8-second clips with audio, Pro and above) next to Magic Media video (4 s, silent), Magic Video auto-edit and Magic Switch — [Morphed](https://morphed.app/blog/canva-ai-video-maker).

#### Other names that surfaced (newcomers / adjacent; not evaluated)
- **Morphic:** hosts GPT Image 2, Seedream 5 and Runway Aleph, with Seedance 2.0 guides — [Morphic](https://morphic.com/resources/models/gpt-image-2).
- **Melies:** model comparison pages — [Melies](https://melies.co/compare/nano-banana-2-vs-nano-banana-pro).
- **Node-canvas challengers:** Astorie, Wireflow, Imaginode — [Astorie](https://astorie.ai/en/vs/flora); [Wireflow](https://www.wireflow.ai/figma-weave-alternative); [Imaginode](https://imaginode.ai/en/vs/artlist).
- **Mage.space:** Characters feature — [Mage](https://blog.mage.space/article/best-ai-image-generators-consistent-characters-2026/392f47f0-6619-4021-9b07-ba3ed8c86ba8).
- **Runway** is reportedly turning Gen-4.5 into a "multi-model creative router for teams", i.e., becoming an aggregator itself — [AlphaSignal](https://alphasignal.ai/news/runway-turns-gen-4-5-into-a-multi-model-creative-router-for-teams) (headline only); [Releasebot (Runway Sept 2026 notes)](https://releasebot.io/updates/runwayai).
- **Luma** publishes pages on competitors' pricing (Higgsfield, Weave) — [Luma](https://lumalabs.ai/news/higgsfield-pricing).

### Inferences
- **Credits are not comparable across platforms.** The units differ: credits, Krea compute units, Leonardo fast tokens, Flora's dollar budget, Midjourney GPU-hours. The only fair comparison is **cost per second of finished video** at a given model and resolution. Examples from the figures above:
  - Magnific: Veo 3.1 4K with audio ≈ 520 credits/s.
  - Hedra: 6 credits/s.
  - Invideo: 0.67–0.8 credits/s.
  - Pollo: Seedance 2.5 at 480p = 6 credits/s.
- **What "unlimited" usually means:** a specific older or lower-resolution model, relaxed or queued speed, or an undisclosed fair-use cap. Magnific's list (Nano Banana 2 plus Kling 2.5 at 720p/5 s) is the most concretely specified. Higgsfield's is the most complained about. ImagineArt's limits are undisclosed.
- **Higgsfield:** if a beginner tries it at all, they should pay monthly (never annually), screenshot the plan terms, and expect throttling. That follows from the 7-day refund window, the reported repricing and the documented controversies.
- **Audio:** wordless stories need music and SFX, not voice. That favours suites bundling audio — Artlist (music and voice in one credit pool), Firefly (ElevenLabs as a partner model), Magnific (audio tools) — over avatar and lip-sync suites (Hedra, Invideo's avatar features).

### Gaps
- **Higgsfield:** which plan ladder is current, what Popcorn, Cinema Studio and Soul ID do, per-video credit costs, and commercial-use terms were not retrieved. Unverified background, not to be cited: in 2025 Popcorn produced multi-frame consistent storyboards from references, and Soul ID trained a character from photos.
- **Magnific Spaces** (node canvas) features were not retrieved, nor whether the EUR prices include VAT.
- **Commercial-use terms** for OpenArt, Higgsfield, Pollo, ImagineArt, Dreamina and Midjourney were not retrieved.
- **Per-video credit costs** for Krea, OpenArt, Artlist, Kaiber, Higgsfield and Google Flow were not retrieved. Unverified background: in 2025 Flow charged AI Pro users about 20 credits per Veo Fast clip and 100 per Quality clip; 2026 values unknown.
- **Trustpilot ratings** for platforms other than Higgsfield were not retrieved.

---

## 4. Which single platform or combination currently gives a beginner the best value for a few 15–60 s videos per week? What do reviewers and communities recommend?

### Takeaway
No retrieved source answers this directly, and community threads could not be retrieved. Based on reported prices, the best-value setups are:
- **(a)** One **~€20–35/month subscription** that covers both keyframes and video, ideally with **genuinely unlimited draft models**: Magnific Premium+ (€25.50/mo on annual billing; Nano Banana 2 and Kling 2.5 720p unlimited). Alternatively a big-brand bundle: Google AI Pro ($19.99; Nano Banana Pro plus Flow/Veo 3.1) or ChatGPT Plus ($20; GPT Image 2.x storyboards).
- **(b)** Cheap pay-per-second **Seedance via Dreamina** for final shots.
- Plus a free editor (e.g., CapCut).
- Avoid annual prepayment on fast-repricing platforms such as Higgsfield, and avoid avatar/lip-sync tools for wordless content.

### Cited Findings (facts relevant to the value calculation)
- **Dreamina:** about $1.29 per 720p 8-second clip ($1.06 on Fast), "the lowest among compared platforms" — [PriceMyAI](https://pricemyai.com/pricing/dreamina/). Seedance 2.5 from $0.035/s at 720p during the promo ending 9 Oct 2026 — [Dreamina](https://dreamina.capcut.com/seedance/seedance-2-5-pricing-2026).
- **Magnific Premium+** (€25.50/mo on annual billing): unlimited Nano Banana 2, unlimited Kling 2.5 at 720p/5 s, plus 600K credits/year for premium models — [AutoKeyWorder](https://autokeyworder.com/blog/magnific-pricing/); [Oakgen](https://oakgen.ai/blog/magnific-ai-freepik-rebrand-pricing).
- **Google AI Pro** ($19.99): 1,000 Flow credits/month and 100 Nano Banana Pro redos/day — [Digital Applied](https://www.digitalapplied.com/blog/google-ai-plans-free-plus-pro-ultra-2026); [AIFreeAPI](https://www.aifreeapi.com/en/posts/nano-banana-pro-rate-limits).
- **ChatGPT Plus** ($20) unlocks GPT Image 2 "Thinking" mode, including multi-image batches of up to 8 consistent images — [BuildFastWithAI](https://www.buildfastwithai.com/blogs/chatgpt-images-2-0-gpt-image-2-2026); [MindStudio](https://www.mindstudio.ai/blog/what-is-gpt-image-2).
- **Krea Pro** ($35): about 257 Nano Banana 2 images (≈$0.14 each) — [Costbench](https://costbench.com/software/ai-image-generators/krea/).
- **OpenArt Plus** ($34/mo, about $17 on annual billing): 40 character slots and 17 One-Click Stories — [Affmaven](https://affmaven.com/openart-pricing/).
- **Pollo Lite** ($15): 400 credits. Seedance 2.5 at 480p costs 30 credits per 5 s, so about 13 clips (≈67 s) per month; Pollo 2.5 costs 5 credits per 5 s, so about 400 s — [Toolstacker](https://toolstacker.io/pollo-ai-pricing).
- **Hedra Basic** ($15): 1,500 credits at 6 credits/s ≈ 250 s of Character-3 per month — [AIYogeum](https://aiyogeum.com/en/tools/hedra).
- **Free options:** Ideogram Character (from one photo) — [Ideogram](https://ideogram.ai/features/character/). Gemini app: Nano Banana 2 plus about 2–4 Nano Banana Pro images/day — [AIFreeAPI](https://www.aifreeapi.com/en/posts/nano-banana-pro-free). Dreamina daily free credits — [PriceMyAI](https://pricemyai.com/pricing/dreamina/).
- **No rollover:** monthly credits don't carry over at Higgsfield, Invideo, Pollo (plan credits), ImagineArt or Hedra — sources in section 3.
- **Annual-plan risk:** a $384 annual Higgsfield plan was lost under a 7-day cancellation policy — [Trustpilot](https://ca.trustpilot.com/review/higgsfield.ai?page=2).

### Inferences
- **Volume estimate (my own assumptions, not from a source):**
  - 3 videos/week × ~30 s ≈ 6 minutes of finished footage per month.
  - With 3–4 generations per kept shot, that means about 18–24 minutes (1,100–1,450 s) of generated video per month.
  - At about $0.13–0.16/s (Dreamina's standard per-clip figures) that is roughly $140–230/month; at the Seedance 2.5 promo rate ($0.035/s) about $40–50.
  - **Consequence:** a $15–35 credit plan covers only about 1–5 minutes of premium video. Iteration has to happen on images (storyboard first) and on cheap or unlimited draft video models, and the premium model should only animate approved keyframes.
- **Scenario A — learning, ≈ €0–10/month:**
  - Keyframes: Gemini app (Nano Banana 2 free, plus a few Nano Banana Pro images/day) or Ideogram Character (free).
  - Video: Dreamina free daily credits or a first-month promo for Seedance.
  - Editing, music and text: CapCut.
- **Scenario B — one subscription, ≈ €20–35/month:**
  - **Magnific Premium+ on annual billing** (≈€25.50/mo reported) for unlimited Nano Banana 2 keyframes and unlimited Kling 2.5 drafts, with credits kept for a few premium shots.
  - **Or Google AI Pro**, if they want one big-brand ecosystem (Nano Banana Pro plus Flow Ingredients and first/last frame on Veo 3.1).
  - **Or OpenArt Plus**, if they want ready-made character slots and One-Click Story scaffolding.
- **Scenario C — ≈ €40–70/month:** Google AI Pro or ChatGPT Plus for character sheets and storyboards, plus a video-first plan for final shots (Kling, Dreamina or Seedance; native pricing is covered by the other researcher).
- **Billing advice for all scenarios:** start monthly, switch to annual only after 2–3 months of steady use, and prefer platforms whose "unlimited" models are named explicitly.

### Gaps
- **No community consensus retrieved** (r/aivideo, r/generativeAI, YouTube reviewers) on the best-value platform in 2026, and no French reviewers' opinions — the search budget ran out before these queries.
- **The 3–4× retake ratio is an assumption**, not sourced.
- **Real per-video costs are unknown** for Google Flow (credits per Veo 3.1 clip in 2026), Krea video, OpenArt video and Higgsfield video.

---

## 5. Availability and pricing in France/EU (EUR, VAT), and whether a VPN is needed

### Takeaway
Very little France-specific information could be retrieved. Only two EUR prices were confirmed: **Canva Pro €110/year** (Sept 2026) and **Magnific Premium+ €25.50/month on annual billing**. Most platforms list USD prices. How EU VAT is applied, and whether any tool needs a VPN from France, could not be verified.

### Cited Findings
- Canva Pro: **€110/year** for one person on Canva's euro pricing page (as of 29 Sep 2026) — [Grafista](https://grafista.io/blog/posts/canva-pro).
- Magnific Premium+: **€25.50/mo on annual billing**, which conflicts with the reported $33.75/mo USD equivalent — [AutoKeyWorder](https://autokeyworder.com/blog/magnific-pricing/); [Oakgen](https://oakgen.ai/blog/magnific-ai-freepik-rebrand-pricing).
- Google AI Pro was found only in USD ($19.99/mo); no EUR price was found — [Digital Applied](https://www.digitalapplied.com/blog/google-ai-plans-free-plus-pro-ultra-2026).
- Dreamina promotions are region-specific (e.g., a "US introductory payment of $1.50") — [Dreamina](https://dreamina.capcut.com/seedance/seedance-2-5-pricing-2026).
- Headlines only:
  - "Seedance 2.0 Is Now Global… Content Restrictions Explained" — [MindStudio](https://www.mindstudio.ai/blog/seedance-2-global-release-platforms-restrictions).
  - "Sora Gets Character Cameos, Invite-Free Access, And Expands To New Markets" (late 2025, no EU detail) — [BGR](https://www.bgr.com/2011808/sora-character-cameos-invite-free-access-new-markets/).
  - "Black Forest Labs FLUX: Versions, Benchmarks & EU Availability" (content not retrieved) — [innFactory](https://innfactory.ai/en/ai-models/flux/).
- One French site covers Kaiber in English — [VideoIA.fr](https://videoia.fr/en/kaiber-ai-review/).

### Inferences
- Most of these tools are web-based aggregators billed in USD by card. A French buyer should expect the checkout total to differ from the USD sticker price once currency conversion and VAT are applied, and should check the checkout page. This is unverified general expectation, not a sourced fact.
- Platforms that show EUR prices (Magnific, Canva) give a French beginner more predictable costs.

### Gaps
- **EUR prices not retrieved** for Midjourney, Google AI Pro, ChatGPT Plus, Higgsfield, Krea, OpenArt, Firefly, Artlist and LTX Studio. Unverified background, do not cite: Google AI Pro was about €21.99/mo and ChatGPT Plus about €23/mo (VAT included) in France in 2025.
- **Availability from France without a VPN** is unconfirmed (Oct 2026) for the Sora app and Sora character cameos, Google Flow, Dreamina/Seedance, and Google AI Plus.
- **How VAT is handled** (included or added) is unconfirmed for every platform.
- **No French-language media** (Les Numériques, Numerama, BFM Tech, Frandroid) were retrieved on these tools — search budget exhausted.
- **Background not verified in this session:** Magnific/Freepik is a Spanish (EU) company and Black Forest Labs is German, which may matter for GDPR-minded users.
