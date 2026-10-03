# Open-source / local AI video ecosystem and niche AI-creator communities (state as of 2026-10-03), for a French-speaking beginner making wordless emotional micro-story videos for TikTok

Legend: [>6 mo] = source or fact older than ~April 2026, so it may be out of date. "Secondary" = search-engine summary or aggregator, not the primary source. Most primary facts below come from GitHub READMEs, licence files and official repos fetched on 2026-10-03 (GitHub was reachable; Hugging Face, Reddit, Wikipedia, comfy.org, docs.comfy.org and artificialanalysis.ai were blocked by the research proxy, and the session's web-search budget ran out partway through).

## 1. Which open-weights video models exist in October 2026 (versions, licences, quality vs closed models, anime suitability, I2V / first-last frame / character LoRAs)?

### Takeaway
In October 2026 the open-weights frontier has three main families. **LTX-2.5** (Lightricks, 11 Aug 2026, 22B, generates audio and video together, community licence that is free under $10M revenue) and **MiniMax H3** (3 Aug 2026, 33B, audio+video, reportedly top-3 on Artificial Analysis) are near closed-model quality. The **Wan 2.2** family (Apache-2.0) is the most widely used. Alibaba stopped releasing open base models after Wan 2.2: Wan 2.5, 2.6 and 2.7 are API-only. It still ships Apache-2.0 specialist models such as Wan-Animate-2 (Aug 2026). **Licensing is a trap for a user in France.** The open-weights licences of HunyuanVideo 1.5 (Tencent) and MiniMax H3 exclude the EU, so the safe options are Wan, LTX-2.x, Kandinsky 5 (MIT), AniSora (Apache-2.0) and Bernini-R (Apache-2.0). For anime, the strongest open option is Bilibili's **AniSora V3.x** (built on Wan) or Wan/LTX with anime style LoRAs.

### Cited Findings

#### Alibaba Wan family (the community default)
- Wan 2.1 timeline: weights and inference code released 25 Feb 2025; ComfyUI integration 27 Feb 2025; **FLF2V-14B (first-last-frame-to-video, 720P)** released 17 Apr 2025; **VACE** ("an all-in-one model for video creation and editing", 1.3B at 480P and 14B at 480/720P) released 14 May 2025. T2V-1.3B needs "only 8.19 GB VRAM" and makes a 5-s 480P clip on an RTX 4090 in about 4 minutes. Licence: Apache 2.0. [>6 mo] — [Wan2.1 GitHub](https://github.com/Wan-Video/Wan2.1)
- Wan 2.2 timeline: TI2V-5B released 28 Jul 2025, with ComfyUI and Diffusers integration the same day. The family includes T2V-A14B and I2V-A14B (MoE, 480P and 720P), S2V-14B (speech-to-video, 26 Aug 2025), Animate-14B (character animation and replacement, 19 Sep 2025) and Diffusers integration of Animate (13 Nov 2025). TI2V-5B runs on a 24 GB card such as the 4090, at under 9 minutes per 5-s 720P clip. The official minimum for single-GPU A14B inference is 80 GB, before community optimisations. Licence: Apache 2.0. **The repo has no 2026 news entries.** — [Wan2.2 GitHub](https://github.com/Wan-Video/Wan2.2)
- The Wan-Video GitHub organisation, checked 2026-10-03, contains Wan2.2 (updated 21 Sep 2026), Wan2.1, Wan-Dancer (Jul 2026), Wan-Animate-2 (Aug 2026), Wan-skills and a diffusers fork. **There is no Wan2.5, 2.6, 2.7 or Wan3 repository.** All listed repos are Apache-2.0. — [Wan-Video GitHub org](https://github.com/Wan-Video)
- **Wan-Animate-2** (released 7 Aug 2026, 14B, Apache 2.0, weights at `Wan-AI/Wan2.2-Animate-2-14B`) is an end-to-end character-animation model driven by a reference image plus a driving video. It preserves identity "without intermediate motion extractors", supports text-driven viewpoint control, and has a real-time "Lite" variant and a 10-step distilled variant. The examples include a stylised cat character. It was tested on 8×A800 at 720P and 2×A800 at 480P. **ComfyUI support was still on the "Todo" list when fetched.** — [Wan-Animate-2 GitHub](https://github.com/Wan-Video/Wan-Animate-2)
- **Wan-Dancer-14B** (Apache 2.0, weights on Hugging Face and ModelScope; the arXiv number 2607.x implies July 2026) generates dance videos longer than one minute at 720p/30 fps, synced to music, in five genres. It was tested on 8×A800 80GB. — [Wan-Dancer GitHub](https://github.com/Wan-Video/Wan-Dancer)
- Wan 2.6 (Dec 2025) "is not open source, is not open-weight", and is sold as an API through Alibaba Cloud Bailian (Model Studio) — [wan27.org (unofficial site, secondary)](https://www.wan27.org/blog/wan-2-6-open-source-guide). One article is headlined "The Newest Wan You Can Download Is Still Wan 2.2" — [howaiworks.ai (secondary)](https://howaiworks.ai/blog/alibaba-wan-open-weights-stopped-at-2-2)
- Wan 2.7 launched in April 2026 as API-only, with a "thinking mode" and closed weights — [tellers.ai, 15 Apr 2026](https://tellers.ai/blog/wan_2_7_thinking_mode_ai_video_generation_2026-04-15). As of 2 Sep 2026, Alibaba documented Wan 2.7 only through hosted Model Studio, with no weights on official channels — [queststudio (secondary)](https://queststudio.io/blog/wan-2-7-open-source); [nemovideo (secondary)](https://www.nemovideo.com/blog/wan-2-7-open-source). Together AI added Wan 2.7 (T2V, scene continuation, editing, audio input) as a hosted model in April 2026 — [inAI-wiki digest 2026-04-04](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2026-04-04.md). "WAN 2.7-Image" was also offered on fal — [inAI-wiki digest 2026-04-02](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2026-04-02.md)
- **Conflicting information to watch for:** several 2026 SEO sites claim Wan 2.7 "returned to an open-weight release in March 2026" ([wan27.org](https://wan27.org/blog/wan-2-7-release-date-open-source), [computertech.co](https://computertech.co/wan-2-7-review/)), and one roundup lists Wan 2.7 as a local model ([thundercompute](https://www.thundercompute.com/blog/best-open-source-ai-video-generation-models)). The official Wan-Video org and the dated reports above contradict these claims. Third-party sites also mention a "Wan 3.0" ([wan27.org](https://wan27.org/blog/wan-3-open-source)), which could not be verified.
- Closed Wan 2.7 features include 9-grid image input, first/last-frame control and 5,000-character prompts — [thundercompute (secondary)](https://www.thundercompute.com/blog/best-open-source-ai-video-generation-models)
- The Wan derivatives and adapters gathered in Kijai's ComfyUI-WanVideoWrapper include SkyReels v2, WanVideoFun, WanAnimate, VACE, ReCamMaster (camera motion), Phantom, MultiTalk/InfiniteTalk (talking heads), Lynx, FantasyTalking/FantasyPortrait, HuMo, SteadyDancer, One-to-All-Animation, TimeToMove, SCAIL, ATI, Uni3C, MoCha, EchoShot and Stand-In — [Kijai ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)

#### Lightricks LTX-2 family (open audio+video)
- The licence directory lists the **"LTX-2 Community License Agreement" dated 5 Jan 2026** (initial LTX-2 open release) and the **"LTX-2.x Community License Agreement" dated 11 Aug 2026** — [LTX-2 LICENSE index](https://github.com/Lightricks/LTX-2/blob/main/LICENSE)
- Under the LTX-2.x licence, organisations with annual revenue above $10,000,000 need a paid Commercial Use Agreement. The licence has **no geographic exclusions** and references EU AI Act compliance. It forbids non-consensual deepfakes, misleading content without disclaimers, content exploiting minors, and similar uses. "Licensor claims no rights in the Output you generate." — [LTX-2.x licence](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x). Lightricks and the press describe it as free for commercial use below $10M ARR — [thedeadpixelssociety (secondary)](https://thedeadpixelssociety.com/lightricks-open-sources-ltx-2-the-production-ready-audio-and-video-generation-model/). Note that the fetch summary of the licence text said "non-commercial" for small entities. Re-read the licence before relying on either reading.
- The current repo lists **LTX-2.5 as the recommended model and LTX-2.3 as legacy**. It ships a distilled 22B transformer (about 12 steps) and a dev 22B transformer, FP8 quantisation, and CPU or disk offload. Supported modes are T2V, I2V, audio-to-video, V2V and **keyframe interpolation**, up to 3840×2176, with HDR/EXR and "Dub-It" lip-sync dubbing. The trainer supports LoRA, full fine-tuning and IC-LoRA. — [LTX-2 GitHub](https://github.com/Lightricks/LTX-2)
- **LTX-2.5** was released 11 Aug 2026 with downloadable weights the same day. It is a 22B model that adds native multi-shot generation, audio-synced clips up to 20 s (LTX-2.3 managed about 10 s) and native 4K HDR. It ships as a full trainable transformer plus a distilled model. — [comfyui-wiki news (secondary)](https://comfyui-wiki.com/ja/news/2026-08-11-ltx-2-5-open-weights-release); [Magica (secondary)](https://magica.com/news/ltx-2-5-open-weight-video-world-model). A community GGUF build exists ("LTX-2.5-Distilled-GGUF", chfm on Hugging Face), per search listings.
- **LTX-2.3** is a 22B diffusion transformer generating synchronised audio and video at up to native 4K/50 fps in clips of about 10 s, with portrait (vertical) support — [invideo blog, updated Aug 2026 (secondary)](https://invideo.io/blog/ltx-ai-video-generator/). As of early 2026 it was "the highest-ranked open-source model in the Artificial Analysis benchmark" — [thundercompute (secondary)](https://www.thundercompute.com/blog/best-open-source-ai-video-generation-models). The original LTX-2 is listed at 19B — [SimpleTuner docs](https://github.com/bghira/SimpleTuner/blob/main/documentation/quickstart/index.md)
- **Conflicting information:** some roundups say LTX-2.3 ships under Apache 2.0 ([sevenlabs](https://www.sevenlabs.site/blogs/best-open-source-video-generation-models-2026)). That is wrong for LTX-2.x, which uses the community licence above. The older LTX-Video 0.9.x was OpenRAIL-M per SimpleTuner.
- The official ComfyUI-LTXVideo nodes require a "CUDA-compatible GPU with 32GB+ VRAM" and provide low-VRAM loaders "such that generation fits in 32 GB". They also include IC-LoRA workflows (union depth+edges control, motion tracking, HDR conversion, Dub-It, 2×/4× pixel upscaling), text-to-audio and a V2V detailer. LTX-2 is built into ComfyUI core. — [ComfyUI-LTXVideo GitHub](https://github.com/Lightricks/ComfyUI-LTXVideo)

#### MiniMax H3 (Hailuo 3), 2026's biggest open newcomer, but EU-excluded
- MiniMax announced H3 on 31 Jul 2026 as API-only, then put weights on Hugging Face on 3 Aug 2026 (`MiniMaxAI/MiniMax-H3`, plus a ComfyUI repack at `Comfy-Org/MiniMax-H3`). It is a 33B model with native stereo audio, 4–15 s output, native 768p with a 2K regeneration workflow, and ships as FL2VA (text-to-audio-video plus first/last-frame) and Ref2VA (reference-to-audio-video) variants. It reportedly ranks **#1 in video editing, #2 in text-to-video and #3 in image-to-video on Artificial Analysis** — [search summary of HF blog / Oxen / RunPod / Atlas Cloud (secondary)](https://huggingface.co/blog/ResterChed/minimax-h3-hailuo-3-0); [RunPod blog](https://www.runpod.io/blog/minimax-h3-the-open-weight-omni-modal-video-model-and-what-it-takes-to-run-it)
- Official repo details: a 33B dense transformer, CFG-distilled. Stereo audio at 32 kHz. FL2VA takes 0, 1 or 2 images. Ref2VA takes up to 9 images, 3 video clips and 3 audio clips (12 files maximum). Output goes up to 2K, with 768 px as the default short side, at 4–15 s and 24 fps. SGLang deployment on 4 GPUs is recommended. — [MiniMax-H3 GitHub](https://github.com/MiniMax-AI/MiniMax-H3)
- **Licence:** commercial use is allowed for companies with ≤$20M yearly revenue, but "You need to explicitly acquire a MiniMax H3 commercial license if you want to use MiniMax H3 in the United States, European Union, United Kingdom, or South Korea, which are excluded from the H3 Community License" — [Comfy Org website licence FAQ (code)](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/apps/website/src/data/minimaxLicense.ts). Civitai's own code states: "Generation, training and LoRA distribution on Civitai are covered by Civitai's own license agreement with MiniMax. If you download these weights and run them yourself… [the licence] excludes the European Union, the United Kingdom, the Republic of Korea and the United States" — [Civitai source code](https://github.com/civitai/civitai/blob/main/packages/civitai-shared/src/basemodel.constants.ts); also [SimpleTuner footnote 12](https://github.com/bghira/SimpleTuner/blob/main/documentation/quickstart/index.md)
- Ecosystem support: native ComfyUI support from v0.34.0 (26 Aug 2026) — [ComfyUI releases](https://github.com/comfyanonymous/ComfyUI/releases). LightX2V offers 4-step "MiniMax-H3 Turbo" distilled LoRAs (Aug 2026) — [LightX2V](https://github.com/ModelTC/LightX2V). SwarmUI and Wan2GP also support it ([SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI), [Wan2GP](https://github.com/deepbeepmeep/Wan2GP)). There is a community "awesome" list with turbo LoRAs, INT8 builds and field reports from RTX 3060 12GB and RTX 5090 users — [awesome-minimax-H3](https://github.com/wildminder/awesome-minimax-H3)

#### Tencent HunyuanVideo 1.5 (good and efficient, but its licence excludes the EU)
- Released 20 Nov 2025. The model has 8.3B parameters and needs a minimum of 14 GB VRAM with offloading. It does T2V and I2V at 480p/720p, up to 121 frames (about 5 s at 24 fps). Later updates added cache inference (27 Nov), a 480p I2V step-distilled model plus open LoRA training code (5 Dec), and FP8 GEMM (23 Dec). With step distillation, end-to-end time drops by 75% and clips render "within 75 seconds" on an RTX 4090. ComfyUI is supported. [>6 mo] — [HunyuanVideo-1.5 GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)
- **Licence:** the Tencent Hunyuan Community License "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA". Services above 100M monthly active users need a separate licence. — [HunyuanVideo-1.5 LICENSE](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE)
- LightX2V ships HunyuanVideo-1.5 distilled models claiming about a 25× speedup — [LightX2V](https://github.com/ModelTC/LightX2V)

#### Other open models
- **Kandinsky 5.0** (kandinskylab / Sber). Video Lite is 2B (T2V at 5 s and 10 s, a 16-step distilled version, I2V Lite at 5 s; latency 35–224 s). Video Pro is 19B (T2V 5/10 s, I2V 5 s; latency 560–1,241 s). There are also 6B image and image-editing models. It needs 12 GB minimum with offloading and outputs 768×512 to 1280×768. Video Pro was released 20 Nov 2025 and was self-reported as "#1 open-source T2V" on 12 Dec 2025. LoRA training is supported (including camera-control LoRAs), and there is a ComfyUI integration folder. **Licence: MIT.** [>6 mo] — [Kandinsky-5 GitHub](https://github.com/kandinskylab/kandinsky-5); MIT is confirmed by [SimpleTuner](https://github.com/bghira/SimpleTuner/blob/main/documentation/quickstart/index.md); one source says Apache 2.0 instead ([Apatero (secondary)](https://apatero.com/blog/kandinsky-5-0-complete-guide-t2i-t2v-i2v-2025)). An official ComfyUI template "Kandinsky 5.0 Video Lite Image to Video" exists, with a French page — [comfy.org/fr workflow](https://comfy.org/fr/workflows/video_kandinsky5_i2v-56e17946ef8c/)
- **SkyReels V3** (Skywork). Weights and code were released 29 Jan 2026. Models: R2V 14B 720P (multi-subject reference-to-video), V2V 14B 720P (video extension) and A2V 19B 720P (audio-driven talking avatar). It needs 24 GB minimum, with a `--low_vram` FP8 mode at 540P/480P. The repo has a licence file, but its terms were not extracted. SkyReels V2 (Apr 2025, "infinite-length", with video extension and frame control from May 2025) is in the same repo. — [SkyReels-V3 GitHub](https://github.com/SkyworkAI/SkyReels-V3). SkyReels V4 is described as a "unified video-audio" model; its open status is unknown — [WaveSpeed (secondary)](https://wavespeed.ai/blog/posts/what-is-skyreels-v4/)
- **Bernini-R** (ByteDance) is a "renderer-only Wan 2.2 model for in-context image and video conditioning". Reference images or videos act as visual prompts, with "no LoRA training or fine-tuning required". It covers generation, editing, relighting, restyling and subject insertion. Builds come in fp16, fp8 and int8. Licence: Apache-2.0. ComfyUI supports it natively (`Comfy-Org/Bernini-R`). A speech-driven S2V variant came out on 9 Jul 2026. — [ComfyUI docs](https://docs.comfy.org/tutorials/video/bytedance/bernini-r); [comfyui-wiki (secondary)](https://comfyui-wiki.com/en/models/bernini/bernini-r); [Bernini-R S2V news](https://comfyui-wiki.com/en/news/2026-07-09-bernini-r-s2v-speech-driven-video)
- **MAGI-1** (Sand AI) is a "fully open-source autoregressive model" for chunk-based video with timing control [>6 mo, Apr 2025] — [Hyperstack roundup (secondary)](https://www.hyperstack.cloud/blog/case-study/best-open-source-video-generation-models). The same roundup lists Mochi 1, CogVideoX, SkyReels V1 and Waver 1.0 among 2026 open models. ComfyUI core still supports CogVideoX, Mochi and NVIDIA's Cosmos Predict2 — [ComfyUI README](https://github.com/comfyanonymous/ComfyUI). These are legacy-tier for a 2026 beginner.
- Other 2026 open releases: Wan2GP's model list includes LongCat and MagiHuman — [Wan2GP](https://github.com/deepbeepmeep/Wan2GP). "daVinci-MagiHuman" (lip-synced human clips in six languages) appeared on fal, and Netflix published its first public model and the open "VOID" video-editing project (Apr 2026) — [inAI-wiki 2026-04-04](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2026-04-04.md). NVIDIA's Sana Video is Apache-2.0 — [SimpleTuner](https://github.com/bghira/SimpleTuner/blob/main/documentation/quickstart/index.md). "FastWan-QAD" (a 1.3B model on a Wan2.1 base) makes a 5-s 480p clip in 1.8 s end to end on an RTX 5090. "FastMetal-5B-QAD" (a Wan 2.2 TI2V-5B INT8 build) targets Apple Silicon with 16 GB+ at 720p/121 frames, under Apache 2.0, with no published benchmark — [radar-huggingface-dataset notes (Spanish, secondary)](https://github.com/686f6c61/radar-huggingface-dataset/blob/main/data/fastvideo/fastmetal-5b-qad.md)

#### Anime / 2D / stylised
- **Bilibili Index-AniSora**, by version:
  - V1: CogVideoX-5B base.
  - V2: Wan2.1-14B base; Apache-2.0 weights, 11 Jul 2025.
  - V3: Wan2.1-14B; open-sourced 27 Aug 2025 under Apache 2.0; style transfer and 1080p super-resolution.
  - V3.1: 4 Sep 2025; a 12 GB VRAM build was uploaded 25 Sep 2025.
  - **V3.2: 23 Sep 2025, Wan2.2-14B base, 8-step inference.**
  - "anymask" model: 31 Oct 2025.

  Features: image-to-video, first/last-frame guidance, keyframe interpolation, pose/depth/**line-art**/audio guidance, 360° character rotation and 90p→1080p super-resolution. It covers anime TV series, Chinese animation, manga, VTuber content and PVs. V3 makes "5 sec 360p video shot within 8 sec". Weights are at `IndexTeam/Index-anisora` on Hugging Face and ModelScope. The repo does not mention ComfyUI. [>6 mo] — [Index-anisora GitHub](https://github.com/bilibili/Index-anisora). It was trained on 10M+ clips from 1M raw animation videos, and the paper was accepted at IJCAI'25 — [comfyui-wiki (secondary)](https://comfyui-wiki.com/en/models/wan/anisora)
- The Banodoco community trained LTX 2.3 **style LoRAs** for Pixar/CGI, Golden Age comics, anime (34,000+ steps), fantasy puppet, **cel animation**, **paper cutout** and dark fantasy. They also trained IC-LoRAs for outpainting, camera-motion transfer, depth control, scene transitions and focus changes. One member found LTX "picks up style quickly but needs extended training for fine character details". — [Banodoco "Cool Stuff People Have Done with LTX 2"](https://github.com/banodoco/brain-of-bndc/blob/main/a.md)
- Closed benchmark: in Nov 2025, Kling 2.5 "generates high-quality, affordable 1080p anime with promptable camera moves like orbit and crash-zoom" — [inAI-wiki 2025-11-11](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/news/2025/2025-11-11.md)

#### Quality versus closed models
- MiniMax H3's reported #2 (T2V) and #3 (I2V) Artificial Analysis rankings in Aug 2026 put an open-weights model inside the top tier — [secondary summary](https://www.oxen.ai/blog/minimax-h3). LTX-2.3 led open models early in 2026 — [thundercompute](https://www.thundercompute.com/blog/best-open-source-ai-video-generation-models)
- Reviewers' opinions: "Wan 2.2 edges out HunyuanVideo on prompt adherence and motion stability"; HunyuanVideo has "the highest output quality among open-source… with cinematic motion coherence"; "No single model is a universal winner" — [thundercompute / sevenlabs (secondary, opinion)](https://www.sevenlabs.site/blogs/best-open-source-video-generation-models-2026)
- Expert hobbyists combine open and closed models. Banodoco members use **Seedance 2.0 (closed)** alongside LTX 2.3, and use **Wan 2.2 to refine LTX outputs** while keeping the lipsync — [Banodoco LTX roundup](https://github.com/banodoco/brain-of-bndc/blob/main/a.md)

#### Image models for keyframes (input to I2V) and their licences
- Z-Image (Tongyi-MAI): Apache-2.0. Flux.2: 32B, with Black Forest Labs non-commercial terms for the dev version; "Klein 4B is Apache-2.0". Qwen Image 2.1 (7B/20B): "Qwen Research" licence, non-commercial per SimpleTuner's table. Kandinsky 5 Image: MIT. — [SimpleTuner](https://github.com/bghira/SimpleTuner/blob/main/documentation/quickstart/index.md). ComfyUI added Qwen-Image 2.1 in v0.37.0 (21 Sep 2026) — [ComfyUI releases](https://github.com/comfyanonymous/ComfyUI/releases)
- Z-Image Turbo renders an image in about 2 s on an RTX 5090 — [Purz's ComfyUI workflow notes](https://github.com/purzbeats/lora_tester/blob/main/.claude/skills/comfy_workflows/skill.md). A FLUX 2 Turbo LoRA preset renders 2048×2048 in about 40 s on an RTX 5090 — [SECourses presets](https://github.com/FurkanGozukara/Stable-Diffusion/blob/main/Generative-AI/Which_Bundles_Downloads_Which_Preset_Models.html). Qwen-Image-Layered (Dec 2025) open-sourced promptable RGBA layer decomposition — [inAI-wiki 2025-12-23](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2025-12-23.md)

#### Audio (essential for wordless stories: ambience, Foley, music)
- Open models with native audio: LTX-2.x (synced audio, 20 s on 2.5) and MiniMax H3 (stereo 32 kHz) — see the sources above.
- **MMAudio** (video-to-audio Foley): code is MIT, but **weights are "CC-BY-NC 4.0", which prohibits commercial use**. About 6 GB VRAM; default length 8 s; last updated Mar 2025 [>6 mo] — [MMAudio GitHub](https://github.com/hkchengrex/MMAudio)
- **HunyuanVideo-Foley**: released 28 Aug 2025, XL model 29 Sep 2025. Produces 48 kHz Foley. The XXL model needs 20 GB (12 GB with offload) and the XL model 16 GB (8 GB with offload). Community ComfyUI nodes exist (if-ai, phazei). The licence was not extracted (see Gaps) [>6 mo] — [HunyuanVideo-Foley GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley)

### Inferences
- For a beginner in France who wants legally clean, commercially usable local generation, the realistic shortlist is: **Wan 2.2** (I2V-A14B, TI2V-5B, plus FLF/VACE from 2.1, plus Animate) under Apache-2.0; **LTX-2.3/2.5** under the community licence (free unless revenue exceeds $10M), the only EU-usable open model with native synced audio; **AniSora V3.2** (Apache-2.0) for anime; **Kandinsky 5** (MIT); and **Bernini-R** (Apache-2.0) for reference-based consistency without LoRA training.
- HunyuanVideo 1.5 and MiniMax H3 are technically excellent, but their open-weights licences do not cover the EU. A French user should reach them only through licensed hosted services, for example Civitai's MiniMax H3 generator, which runs under Civitai's own agreement, or MiniMax's API.
- Alibaba's pattern, with 2.5, 2.6 and 2.7 closed but specialist 14B models still released under Apache-2.0, suggests the newest "flagship" Wan quality will come through APIs, while the open community keeps building on Wan 2.2. This is a trend reading, not a confirmed policy.
- For wordless micro-stories, the most useful open capabilities are image-to-video from carefully designed keyframes, first/last-frame control for shot continuity, reference or LoRA-based character consistency, and native or added ambient audio. All of these exist in open form in late 2026.

### Gaps
- No primary-source Artificial Analysis leaderboard snapshot for Oct 2026 (the domain was blocked), so open-vs-closed rankings rely on secondary summaries from Aug 2026.
- The licence of HunyuanVideo-Foley was not extracted. It is likely the Tencent Hunyuan licence with an EU exclusion, but this is unverified. The SkyReels V3 licence terms were not extracted either.
- The status of "Wan 3.0" (mentioned only by SEO sites) is unknown.
- Primary sources for MAGI-1, Mochi, CogVideoX and Waver in 2026 were not checked; these are likely superseded.
- No 2026 primary data on anime-specific image checkpoints (Illustrious, NoobAI, Pony and others) or their licences.
- Exact LTX-2.x licence wording for small commercial users needs a human read, because the two summaries conflict.

## 2. ComfyUI and alternatives: what it is, learning curve, Desktop, templates, storytelling workflows, API/Partner nodes, Comfy Cloud pricing; Pinokio, Wan2GP, SwarmUI, Forge, InvokeAI

### Takeaway
ComfyUI is the hub of open AI video. It is a free node-graph engine that supports essentially every open model within days of release, has an official Desktop app (Windows/macOS) and a French-localised interface, and bundles "Partner Nodes" that call paid closed models. It shipped roughly a release every two weeks in 2026, reaching v0.38.0 by about 29 Sep 2026. Comfy Cloud runs the same graphs on rented GPUs from $20/month for about 380 five-second clips, and the same credits pay for closed models. For beginners who find node graphs intimidating, **Wan2GP** (low-VRAM all-in-one) and **SwarmUI** (simple "Generate" tab over a ComfyUI backend) are the gentler local alternatives. InvokeAI does images only.

### Cited Findings
- ComfyUI describes itself as "the most powerful and modular AI engine for content creation", built as a visual node graph. Core video support includes Wan 2.1/2.2, LTX-Video 2/2.3, HunyuanVideo 1.5, Kandinsky 5, CogVideoX, Cosmos Predict2, Bernini-R and Mochi. It claims it can "run even the biggest open source models on as low as 4GB vram + 8GB ram" through asynchronous weight streaming, and can also run on CPU only. It runs on Windows, Linux and macOS (Apple Silicon M1–M4) with AMD, Intel or NVIDIA GPUs. The official Desktop app for Windows and macOS is the recommended entry point for new users. "Partner nodes" give access to closed models. Major stable versions come out roughly every two weeks. — [ComfyUI GitHub README](https://github.com/comfyanonymous/ComfyUI)
- Recent releases. The fetch tool printed the year of v0.38.0 as 2024, but the release content (Qwen-Image 2.1, MiniMax-H3) dates them to 2026.
  - v0.34.0 (26 Aug): MiniMax-H3, TRELLIS2 3D and HDR/AV1 video saving.
  - v0.35.0 (9 Sep): "Comfy Compiler" optimisation, HDR video and sparse attention.
  - v0.36.0 (15 Sep): generic loops, **video concatenation and advanced video editing**, and YuE2 music generation.
  - v0.37.0 (21 Sep): Qwen-Image 2.1, MoGe 3 depth and fast disk mode.
  - v0.38.0 (29 Sep): Ming Image, plus support for "Seedream 5.0 Flash" and "GPT-6 Sol/Luna". These are closed models, so probably reached through Partner/API nodes; that is an inference.

  — [ComfyUI releases](https://github.com/comfyanonymous/ComfyUI/releases)
- **French interface:** the ComfyUI frontend ships French locale files (`src/locales/fr/main.json`, `commands.json`, `settings.json`) — [ComfyUI_frontend repo](https://github.com/Comfy-Org/ComfyUI_frontend/tree/main/src/locales/fr). Official workflow-template pages exist in French, for example the Kandinsky 5 I2V template — [comfy.org/fr/workflows](https://comfy.org/fr/workflows/video_kandinsky5_i2v-56e17946ef8c/)
- **Comfy Cloud pricing** (search summary of comfy.org/pricing):

  | Plan | Price | Credits | Approx. 5-s videos | Max runtime | Concurrent API workflows | Notes |
  |---|---|---|---|---|---|---|
  | Standard | $20/month | 4,200 | ~380 | 30 min | 1 | |
  | Creator | $35/month | 7,400 | ~670 | 30 min | 3 | Import your own LoRAs |
  | Pro | $100/month | 21,100 | ~1,915 | 1 hour | 5 | |
  | Enterprise | Custom | – | – | – | – | |

  There are "5 free runs on real GPUs with no credit card". "One credit balance covers both Cloud GPU time and Partner Node API models", and credits are consumed only while the GPU runs. — [comfy.org pricing (search summary)](https://comfy.org/pricing); [Comfy blog: unified credits / bring your own LoRAs](https://blog.comfy.org/p/comfy-cloud-update-unified-credit-system)
- Comfy Org's own website code corroborates this. The pricing page reads "start free with 5 GPU runs, then pick Standard, Creator, Pro, or Team". The test fixtures show 4,200 / 7,400 / 21,100 credits mapping to ~380 / 670 / 1,915 videos, and the Creator plan at 3,500 cents per month. The Pro plan has an education price of $90/month ($75/month billed yearly). The frontend also has an in-app "agent" extension billed against workspace credits. — [pricing.astro](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/apps/website/src/pages/pricing.astro); [website locale (en)](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/apps/website/src/locales/en/main.json); [PricingTableWorkspace.test.ts](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/platform/workspace/components/PricingTableWorkspace.test.ts); [AgentPaywallCard.test.ts](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/workbench/extensions/agent/components/agent/message/AgentPaywallCard.test.ts)
- **Storytelling building blocks available in ComfyUI** (sources as above):
  - **Image-to-video:** Wan 2.2 I2V-A14B and TI2V-5B, LTX-2.x, HunyuanVideo 1.5, Kandinsky 5 I2V, AniSora.
  - **First/last frame:** Wan2.1 FLF2V-14B, LTX keyframe interpolation, MiniMax H3 FL2VA, AniSora.
  - **VACE:** Wan2.1 all-in-one creation and editing.
  - **Character consistency:** LoRAs, LTX IC-LoRAs, SkyReels V3 R2V, Bernini-R, and Phantom / Stand-In / Lynx through Kijai's wrapper.
  - **Motion transfer from a driving video:** Wan-Animate / Animate-2, SteadyDancer.
  - **Lip-sync / talking:** InfiniteTalk, Wan S2V, Bernini-R S2V, LTX Dub-It.
  - **Speed:** LightX2V 4-step distillations.
  - **Upscaling:** LTX pixel-upscaler IC-LoRA (2×/4×) — [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo). LightX2V supports the SeedVR2 and SwiftVR super-resolution models (Sep 2026) — [LightX2V](https://github.com/ModelTC/LightX2V). SeedVR2 v2.5 (Nov 2025) added GGUF builds for 8 GB GPUs — [AInVFX-News (secondary; dates in that summary partly unreliable)](https://github.com/AInVFX/AInVFX-News)
  - **Frame interpolation:** a popular Wan 2.2 preset renders 81 frames at 16 fps and applies **RIFE 2× interpolation by default, giving 5 s at 32 fps** — [SECourses presets](https://github.com/FurkanGozukara/Stable-Diffusion/blob/main/Generative-AI/Which_Bundles_Downloads_Which_Preset_Models.html)
  - **Video-to-audio:** MMAudio and HunyuanVideo-Foley ComfyUI nodes — [HunyuanVideo-Foley](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley)
  - **Long-form:** latent-space looping and multi-minute chaining through first/last-frame continuations with LTX — [Banodoco LTX roundup](https://github.com/banodoco/brain-of-bndc/blob/main/a.md)
- Kijai's ComfyUI-WanVideoWrapper is the "personal sandbox" where new Wan-family models usually appear first, before native ComfyUI support. VRAM tips: block swapping (swap 2 or more extra blocks when adding LoRAs), "fp8 scaled" models and GGUF. Breaking changes do occur: LoRA weights moved to module buffers (about +25 MB VRAM per block for users not swapping blocks), and users are advised to clear Triton caches after updates. — [ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)
- **Wan2GP ("WanGP")** is "a one-stop super app for the best open source generative models" for limited GPUs. It runs some models on "as little as 6 GB of VRAM", on GTX 10xx through RTX 50xx and AMD RDNA 2–4.
  - Video models: Wan 2.1/2.2, MiniMax H3, LTX-2/2.3/2.5, Hunyuan 1/1.5, LongCat, Kandinsky, MagiHuman.
  - Image models: Qwen Image, Z-Image, Flux 1/2, Krea 2 and others.
  - Audio: TTS and music models.
  - Recent versions: v13.10 on 16 Sep 2026 (UI overhaul), v13.1315 on 24 Sep 2026 (Qwen Image 2.1), v13.141 on 29 Sep 2026 (live video previews).
  - Install: Pinokio community scripts by "Morpheus" are recommended over the official Pinokio installer; one-click .bat/.sh scripts also exist. "WanGP is free to use locally."

  — [Wan2GP GitHub](https://github.com/deepbeepmeep/Wan2GP)
- **SwarmUI** (v0.9.8 Beta, MIT licence) states that "Beginner users will love Swarm's primary Generate tab interface", while advanced users can open the full ComfyUI graph. It can auto-install a ComfyUI backend and supports MiniMax H3, Wan and LTX-2. It runs on Windows, Linux, macOS (M-series only), Docker, Google Colab, RunPod and Vast.ai. — [SwarmUI GitHub](https://github.com/mcmonkeyprojects/SwarmUI)
- **InvokeAI** is actively maintained (Apache-2.0) and supports SDXL, Flux and Flux.2, Z-Image, Qwen Image, Krea 2 and more, but **does not support video**. — [InvokeAI GitHub](https://github.com/invoke-ai/InvokeAI)
- **ComfyUI-Easy-Install** is a "one-click portable ComfyUI installer for Windows, macOS and Linux, with EZi Desktop" dashboard, and also a "Pixaroma Community Edition". It had 1,951 stars and was updated 3 Oct 2026. — [Tavris1/ComfyUI-Easy-Install](https://github.com/Tavris1/ComfyUI-Easy-Install)
- Troubleshooting realities reported by power users: diffusers→ComfyUI H3 LoRAs had "swapped fused fc1 halves"; "ComfyUI silently falls back to tiled VAE decode on OOM"; one optimisation "silently changes output" — [awesome-minimax-H3 (field notes)](https://github.com/wildminder/awesome-minimax-H3)

### Inferences
- The learning curve has two parts. Running a built-in template on Desktop is hours of work. Understanding VRAM management, custom nodes, LoRA stacking and model-file placement is weeks of work. The constant release cadence, with new models every few weeks and breaking wrapper changes, means ongoing maintenance rather than a one-time setup. This is an inference from the release cadence and changelogs above; no survey data was found.
- A sensible beginner path is: ComfyUI Desktop or SwarmUI, then official templates (Wan 2.2 I2V, LTX-2.x I2V, first/last frame), then a single LoRA. Custom node wrappers such as Kijai's come only after that.
- Comfy Cloud is effectively the "same skills, no GPU" option. Because Partner Node credits are unified, one subscription can mix open models (Wan/LTX) with closed models in the same graph, which is a natural hybrid for a beginner.

### Gaps
- No primary 2026 data on Stable Diffusion WebUI Forge's status (not checked). Pinokio was only checked indirectly, through the Wan2GP README.
- No quantitative learning-curve data (time to first video, drop-out rates).
- The exact list of built-in ComfyUI video templates as of Oct 2026 is not verified (docs.comfy.org was blocked).
- No euro pricing for Comfy Cloud. Prices are in USD; VAT treatment for French consumers was not verified.

## 3. Hardware and cloud: VRAM per model, quantised/distilled variants, time per 5-s clip on consumer GPUs, Mac support, cloud GPU and API prices

### Takeaway
With 2026 distillations (LightX2V 4–8 steps) and quantisation (FP8/GGUF/INT8), Wan-class 14B video runs on a **12 GB RTX 3060 at about 10–15 min per 5-s clip**. It takes **about 1 minute on an RTX 5090** for 480p with a speed LoRA. HunyuanVideo 1.5 distilled does about 75 s on a 4090. LTX-2.x officially wants 32 GB+, though community low-VRAM paths exist. **Macs are a poor fit for video**: one test took 82 min for a 2-s Wan 2.2 clip on an M1 Max, and FP8 fails on Metal. Renting is cheap: an RTX 4090 costs about $0.15–0.69/h and an RTX 5090 about $0.69–0.99/h. Managed Comfy Cloud works out to about $0.05 per 5-s clip, and per-clip APIs for open models cost about $0.30–0.50 per 5 s.

### Cited Findings

#### VRAM by model
- **Wan 2.1 T2V-1.3B:** 8.19 GB — [Wan2.1](https://github.com/Wan-Video/Wan2.1)
- **Wan 2.2 TI2V-5B:** 24 GB (4090) officially; **A14B** officially 80 GB on a single GPU — [Wan2.2](https://github.com/Wan-Video/Wan2.2). In practice the community runs Wan 2.2 14B on **12 GB (RTX 3060) with the LightX2V LoRA plus BlockSwap** — [Civitai article 17955](https://civitai.com/articles/17955) / [archive](https://civarchive.com/articles/17955/wan-2-2-workflow-optimized-for-rtx-3060-12-gb-vram-gpu)
- **LightX2V** claims it can "run 14B models for 480P/720P video generation with only 8GB VRAM + 16GB RAM". It offers 4-step distilled Wan 2.1/2.2, HunyuanVideo-1.5 (about 25× faster) and MiniMax-H3 Turbo models, with NVFP4/FP8 quantisation — [LightX2V](https://github.com/ModelTC/LightX2V)
- **ComfyUI** claims 4 GB VRAM + 8 GB RAM for "the biggest" models via weight streaming (expect it to be slow) — [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- **Wan2GP** runs some models on 6 GB — [Wan2GP](https://github.com/deepbeepmeep/Wan2GP)
- **HunyuanVideo 1.5:** 14 GB minimum with offloading — [HunyuanVideo-1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)
- **Kandinsky 5:** 12 GB minimum with offloading — [Kandinsky-5](https://github.com/kandinskylab/kandinsky-5)
- **AniSora V3.1:** a 12 GB build exists — [Index-anisora](https://github.com/bilibili/Index-anisora)
- **SkyReels V3:** 24 GB, or a `--low_vram` FP8 mode at 540P/480P — [SkyReels-V3](https://github.com/SkyworkAI/SkyReels-V3)
- **LTX-2.x:** the official ComfyUI nodes want 32 GB+ — [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo). Banodoco members report a "three-pass optimization on 3060 GPU for 241 frames" and LoRA training "accessible on 3060 through 5090" — [Banodoco](https://github.com/banodoco/brain-of-bndc/blob/main/a.md)
- **MiniMax H3:** officially 4 GPUs; community reports exist for an RTX 3060 12GB and a 5090 — [awesome-minimax-H3](https://github.com/wildminder/awesome-minimax-H3)
- **Audio models:** MMAudio about 6 GB — [MMAudio](https://github.com/hkchengrex/MMAudio); HunyuanVideo-Foley XL 8 GB with offload — [Foley](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley)

#### Generation times (5-s clips unless stated)
- **RTX 3060 12GB, Wan 2.2 + LightX2V, 6 steps, upscaled and interpolated to 1440×960 at 60 fps:** about 10–12 min (T2V) and about 15 min (I2V) — [Civitai 17955](https://civitai.com/articles/17955); [secondary summary](https://civarchive.com/articles/17955/wan-2-2-workflow-optimized-for-rtx-3060-12-gb-vram-gpu)
- **RTX 4090:**
  - Wan 2.1 1.3B at 480p: about 4 min — [Wan2.1](https://github.com/Wan-Video/Wan2.1)
  - Wan 2.2 TI2V-5B at 720p: under 9 min — [Wan2.2](https://github.com/Wan-Video/Wan2.2)
  - HunyuanVideo 1.5 step-distilled: about 75 s — [HunyuanVideo-1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)
- **RTX 5090:**
  - Wan 2.2 I2V 14B with a dual LightX2V LoRA, 6 steps, 480p, `torch.compile`: about 60 s. Higher resolutions need BlockSwap or the Kijai wrapper, or fewer frames — [RunPod serverless notes (Russian)](https://github.com/gen4sp/wan22runpodServerLess/blob/main/docs/convers.md)
  - FastWan 1.3B at 480p: 1.8 s — [FastVideo notes](https://github.com/686f6c61/radar-huggingface-dataset/blob/main/data/fastvideo/fastmetal-5b-qad.md)
- **MiniMax H3 on a 5090 + 4090 pair:** a distributed queue cut a full music video from 3.8 h to 2.7 h; there is a "345-frame stall cliff" on the 4090 — [awesome-minimax-H3](https://github.com/wildminder/awesome-minimax-H3)
- **Kandinsky 5:** Lite takes 35–224 s and Pro 560–1,241 s. The hardware is not stated, and the repo was tested on an H100 — [Kandinsky-5](https://github.com/kandinskylab/kandinsky-5)

#### Mac (Apple Silicon)
- ComfyUI supports M1–M4 — [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- SwarmUI supports M-series Macs — [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI)
- Field test on an M1 Max with 64 GB: "FP8 fails on Metal", and a GGUF Wan 2.2 build "takes 82 min per 2-sec clip" — [lilting.ch](https://lilting.ch/en/articles/ltx2-wan22-mac-local-video-gen)
- A Mac-specific INT8 Wan 2.2 5B build ("FastMetal-5B-QAD", 16 GB+) exists, without published benchmarks — [notes](https://github.com/686f6c61/radar-huggingface-dataset/blob/main/data/fastvideo/fastmetal-5b-qad.md)

#### Cloud GPUs (hourly)

| Provider | GPU | Price per hour | Notes | Source |
|---|---|---|---|---|
| RunPod | RTX 4090 | $0.34 (Community) / $0.69 (Secure) | Per-second billing; as of Jun–Aug 2026 | [diyai](https://diyai.io/ai-tools/hosting/runpod-pricing/); [computeprices](https://computeprices.com/providers/runpod/gpus/rtx4090) |
| RunPod | RTX 5090 (32 GB) | $0.69 (Community) / $0.99 (Secure) | As of Jun–Aug 2026 | [computeprices](https://computeprices.com/providers/runpod/gpus/rtx5090) |
| Vast.ai | RTX 4090 | about $0.29–0.31 on demand; about $0.15 interruptible | Updated 5 Aug 2026 | [computeprices](https://computeprices.com/providers/vast/gpus/rtx4090); [costbench](https://costbench.com/software/ai-gpu-cloud/vast-ai/) |
| Unspecified (Banodoco report) | RTX Pro 6000 | $1.89 | Used for LoRA training | [Banodoco](https://github.com/banodoco/brain-of-bndc/blob/main/a.md) |
| RunComfy | H100 / H200 | $4.49 / $5.75 | Training rates; billed per second | [wireflow (secondary)](https://www.wireflow.ai/blog/best-comfyui-cloud-pricing-tools-in-2026) |
| Managed ComfyUI clouds in general | – | about $0.50–2.00 | ThinkDiffusion bills hourly sessions by GPU size; "a light user can spend under $20 a month" | [wireflow (secondary)](https://www.wireflow.ai/blog/best-comfyui-cloud-pricing-tools-in-2026) |

- A French-language guide to RunPod costs exists — [Hackceleration (FR)](https://hackceleration.com/fr/labs/combien-coute-runpod)

#### Per-clip APIs for open models
- fal.ai: Wan 2.2 A14B costs $0.10/s, so a 10-s 720p clip is about $1.00, against $5.00 for Sora 2 Pro at 1080p — [fal (search summary)](https://fal.ai/learn/tools/ai-video-generators)
- LTX-2 Pro: $0.06/s at 1080p, $0.12/s at 1440p, $0.24/s at 2160p — [LTX API pricing](https://ltx.io/model/api/pricing)
- LTX-2.3 Pro official API: $0.08–0.32/s — [invideo](https://invideo.io/blog/ltx-ai-video-generator/)

### Inferences
- These per-clip figures are rough and exclude failed takes, setup time and model downloads:
  - **Comfy Cloud:** $20 ÷ 380 ≈ **$0.05 per 5-s clip**; the Creator and Pro tiers work out about the same.
  - **fal Wan 2.2:** about **$0.50 per 5-s clip**.
  - **Self-rented 5090 at $0.69/h, about 60 s per 480p clip:** about **$0.01–0.02 of GPU time per clip**, but pod start-up, about 30–60 GB of model downloads per fresh pod without a network volume, and idle time can dominate for a beginner.
  - **Local RTX 3060:** about 4–6 clips per hour, at the cost of electricity plus the user's waiting time.
- Combining these with Frank Houbre's "keep rate" (beginners keep about 1 shot in 12, professionals 1 in 3–4; see Q6), a 30–60 s micro-story of 6–12 kept 5-s shots needs about 72–144 generations at beginner level. That fits within one Comfy Cloud Standard month, about 380 runs or roughly 2–5 stories per month at beginner yield, and roughly 9–18 stories per month at professional yield.
- VRAM tiers for planning (inference from the sources above):

  | VRAM | What runs |
  |---|---|
  | 8 GB | Wan 1.3B / TI2V-5B with offload; LightX2V or Wan2GP paths; audio models |
  | 12 GB (3060) | Wan 2.2 14B with GGUF/FP8, LightX2V and BlockSwap; AniSora 12 GB build; Kandinsky with offload. Slow (10–15 min per clip) |
  | 16 GB | Comfortable for 5B models; workable for 14B with quantisation; HunyuanVideo 1.5 (14 GB minimum) |
  | 24 GB (3090/4090) | Most models at FP8; LTX-2.x only through low-VRAM paths |
  | 32 GB (5090) | Officially the comfortable tier for LTX-2.x; about 1 min per Wan clip with distillation |

- Mac users should treat local video generation as impractical and use Comfy Cloud or APIs. Local image keyframes are still feasible on a Mac.

### Gaps
- No 2026 euro street prices for GPUs in France (RTX 5060 Ti 16 GB, 5070 Ti, 4090, 5090) and no French electricity tariff were found, so a local total-cost-of-ownership figure cannot be computed from sources.
- No Google Colab Pro/Pro+ price in euros for 2026, and no evidence on whether Colab's terms still allow ComfyUI.
- No direct timings for RTX 4070 or 4060 Ti 16 GB, or for LTX-2.5 on consumer GPUs.
- RunComfy and ThinkDiffusion hourly inference prices were not obtained from primary pages.
- Replicate per-video pricing for open models was not found.

## 4. Niche communities, learning hubs, YouTube educators, French-speaking resources, festivals and competitions

### Takeaway
The "underground" open-source video scene centres on:
- the **Banodoco Discord**, which runs the open-source-only **Arca Gidan Prize** ($50k; Edition II had 95 films on the theme "Time");
- **Kijai's** wrapper and GitHub;
- **Civitai**, which in 2025–26 split into SFW and adult domains with different "Buzz" currencies and blocked the UK and Australia;
- YouTube/GitHub educators such as **Pixaroma**, **Purz** and **SECourses**.

The festival circuit is booming:
- **Runway AIF 2026**: $135k+ in prizes.
- **Chroma Awards**: $175k pool with Kling in 2025; 6,649 entries.
- **Project Odyssey** (Civitai).
- **WAIFF – World AI Film Festival**: Cannes, Kyoto, São Paulo, Seoul.

On the French side, the clearest verified figure is **Frank Houbre**, a French AI filmmaker. He makes the independent AI anime *Lost Garden*, made *VOIDBORN* (award at the Chroma Awards) and runs the AI Studios training (ai-studios.fr). WAIFF has a Cannes edition, and the ComfyUI interface is available in French.

### Cited Findings

#### Banodoco (open-source AI video hub)
- Banodoco maintains an active Discord. Its "hivemind" repo lets coding agents "search Banodoco's Discord for video/image generation best practices". Its projects include Steerable-Motion (974★, ComfyUI image-batch-to-video), Dough (archived) and **Reigh** (an active video-generation app with a GPU worker). — [Banodoco GitHub](https://github.com/banodoco)
- The **Arca Gidan Prize** is "a one month open source AI film contest, in partnership with Banodoco, ComfyUI, and Lightricks", with winners posted at arcagidan.com/winners — [AInVFX-News README](https://github.com/AInVFX/AInVFX-News)
  - It launched around late Oct 2025 "for open-source AI art" — [inAI-wiki 2025-10-27](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2025-10-27.md)
  - Feb 2026: "$50,000 award" plus "a 4.5 kg Toblerone" — [inAI-wiki 2026-02-27](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2026-02-27.md)
  - **Edition II:** "95 entries, 7,285 votes, on the theme of 'Time'", showcasing LTX. Notable entries include "Everyone All at Once" (visualfrisson), "Archive 113391", "Cherrybomb" and "Synth Study #1" — [Banodoco LTX roundup](https://github.com/banodoco/brain-of-bndc/blob/main/a.md)
  - The entry *INNOCENCE* was "made entirely with open source models", using custom Z-Image and LTX-2.3 LoRAs trained on 20-year-old ink drawings — [AInVFX-News](https://github.com/AInVFX/AInVFX-News)
- Banodoco members built full music videos on a single 4090 with LTX looping workflows (fredbliss). They also built an agentic "FADE Director" pipeline with LLM-driven scene generation (ckinpdx). LoRA training on "just 4 videos at 1000 steps produced 'already big difference'". Key contributors include Kijai, oumoumad, Ablejones and Cseti, and a "thankskijai" tribute video drew 81 reactions. — [Banodoco LTX roundup](https://github.com/banodoco/brain-of-bndc/blob/main/a.md)

#### Kijai
- Kijai's ComfyUI-WanVideoWrapper is the main incubator for Wan-family research models in ComfyUI (see Q2) — [ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)

#### Civitai (LoRA and model sharing; 2025–26 changes, as seen in its public source code)
- **Domains and currencies:** civitai.com uses "yellow buzz", while **civitai.green is a "safe-for-work site" using "green buzz"**. Membership green Buzz "can only be used to generate safe for work content on Civitai.green". — [Civitai auction-buzz plan](https://github.com/civitai/civitai/blob/main/docs/plan-unified-auction-buzz.md); [MembershipTypeSelector](https://github.com/civitai/civitai/blob/main/src/components/Purchase/MembershipTypeSelector.tsx)
- **Region restrictions:** users from restricted regions are redirected to civitai.green — [region-blocking docs](https://github.com/civitai/civitai/blob/main/docs/region-blocking.md). An internal migration plan would make civitai.com the "green" deployment and move the other deployment to **civitai.red**; whether this has gone live is unverified — [environment-swap plan](https://github.com/civitai/civitai/blob/main/docs/plans/environment-swap.md)
- **Country blocks:** "Civitai is no longer accessible to users in the UK due to the Online Safety Act" — [gb-region-block](https://github.com/civitai/civitai/blob/main/src/static-content/gb-region-block.md). Australia is also blocked under the Age-Restricted Material Codes, with civil penalties of up to AUD 49.5M per breach — [au-region-block](https://github.com/civitai/civitai/blob/main/src/static-content/au-region-block.md)
- **Generation:** Civitai offers licensed MiniMax H3 generation, training and LoRA distribution under its own agreement with MiniMax — [Civitai code](https://github.com/civitai/civitai/blob/main/packages/civitai-shared/src/basemodel.constants.ts). In Sep 2025 it offered free SDXL generation without sign-up — [inAI-wiki reddit digest 2025-09-27](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/reddit-news/2025/2025-09-27.md)
- **Project Odyssey** is Civitai's AI-film competition. Season 2 ran 16 Dec 2024 – 16 Jan 2025 with RunPod as gold sponsor [>6 mo] — [NERDDISCO blog](https://github.com/NERDDISCO/nerddis.co/blob/main/content/how-to-prompt-a-genai-video-platform-for-project-odyssey.md). A participant called it the "world's biggest AI film contest", with 4,593 submissions (season unspecified) — [mm-breakdown notes](https://github.com/syverlauritz/mm-breakdown/blob/main/syver/info/Cross-Reference%20Research%20Findings.md). A "Season 3" was listed as upcoming in a contest database, with no date — [eve-creator contests.json](https://github.com/playlist0726-code/eve-creator/blob/main/data/contests.json)

#### Educators visible on GitHub in 2026
- **Pixaroma:** ComfyUI-Pixaroma nodes (repo created 28 Mar 2026, active 3 Oct 2026), plus the "Pixaroma Community Edition" of ComfyUI-Easy-Install — [pixaroma/ComfyUI-Pixaroma](https://github.com/pixaroma/ComfyUI-Pixaroma); [ComfyUI-Easy-Install](https://github.com/Tavris1/ComfyUI-Easy-Install)
- **Purz** (purzbeats): ComfyUI workflow tooling in 2026 — [purzbeats/lora_tester](https://github.com/purzbeats/lora_tester/blob/main/.claude/skills/comfy_workflows/skill.md)
- **SECourses / Furkan Gözükara:** presets and YouTube tutorials for Wan 2.2, FLUX and Qwen — [FurkanGozukara/Stable-Diffusion](https://github.com/FurkanGozukara/Stable-Diffusion/blob/main/Tutorials/Wan-22-FLUX-and-Qwen-Image-Upgraded-Ultimate-Tutorial-for-Open-Source-SOTA-Image-and-Video-Gen-Models.md)

#### French-speaking resources (verified)
- **Frank Houbre** is a French AI filmmaker and entrepreneur. He co-founded Outerframe Studio and created the ScreenWeaver (screenwriting/storyboard) and Imaginode (generation platform) tools. His film **VOIDBORN** won 1st Place Silver at the Chroma Awards, 2nd place at the Dreamina awards and an award at the Seoul International AI Film Festival. *Les Fils du Vinnana* received an honourable mention at the Top Quark Film Festival, and *Lost Garden* was a finalist at the AI London Festival. — [Frank Houbre blog (EN version of a French article, Sep 2026)](https://github.com/Frankhoubre/frankhoubre.com/blob/main/content/blog-en/vivre-video-ia-2026-modeles-revenus.md)
- VOIDBORN's other awards include the Hollywood Indie Festival and the Australian AI Festival — [AI Studios site code](https://github.com/Frankhoubre/ai-studios-formation-ia/blob/main/lib/constants.ts)
- **AI Studios** (blog.ai-studios.fr) offers "Formation IA en image et vidéo" (AI training in image and video, in French) — [repo](https://github.com/Frankhoubre/ai-studios-formation-ia)
- **Imaginode** prices in EUR (Houbre's own platform, so a conflict of interest applies) — [Houbre blog](https://github.com/Frankhoubre/frankhoubre.com/blob/main/content/blog-en/vivre-video-ia-2026-modeles-revenus.md):

  | Plan | Price | Credits | Approx. video |
  |---|---|---|---|
  | Monthly | €13 | ~900 | ~173 s |
  | Monthly | €42 | ~3,100 | – |
  | Monthly | €145 | ~10,500 | – |
  | One-off top-up | €5 | 300 | – |

- **Other French-language resources:**
  - The ComfyUI interface ships a French locale — [ComfyUI_frontend fr](https://github.com/Comfy-Org/ComfyUI_frontend/tree/main/src/locales/fr)
  - Comfy's workflow pages exist in French — [comfy.org/fr](https://comfy.org/fr/workflows/video_kandinsky5_i2v-56e17946ef8c/)
  - Hackceleration publishes a French guide to RunPod costs and advertised a €1,090 intermediate AI bootcamp for Sep 2026 (search-result listing) — [hackceleration.com/fr](https://hackceleration.com/fr/labs/combien-coute-runpod)
  - A French GenAI course repo includes ComfyUI-API notebooks (Qwen-Image-Edit, Forge SDXL Turbo) — [jsboige/CoursIA](https://github.com/jsboige/CoursIA/blob/main/MyIA.AI.Notebooks/GenAI/Image/INDEX.md)
- A Lyon filmmaker, Fabien Loïacono, had an AI short film, "D'ombre et de lumière", shown at Cannes 2026 — [habit-ai weekly W14 (secondary)](https://github.com/habit-ai/behavioral-ai-predictions-2026-public/blob/main/reports/weekly/2026-W14.md)

#### Festivals and competitions
- **Runway AI Festival (AIF) 2026:**
  - Prizes: Grand Prix $50,000 + 1M Runway credits; Gold $15,000; Silver $10,000; two Honoree awards at $1,000; five Merit awards at $500. The announced total across tracks is above $135,000.
  - Categories: Film, New Media, Gaming, Design, Advertising, Fashion. Events in New York, Los Angeles and Tokyo.

  — [Houbre blog citing aif.runwayml.com](https://github.com/Frankhoubre/frankhoubre.com/blob/main/content/blog-en/vivre-video-ia-2026-modeles-revenus.md). *Total Pixel Space* is a Runway AI Film Festival winner (2025) — [talk notes](https://github.com/dongzhuoyao/tao-research-skills/blob/main/docs/videos/2026-03-16-xie-saining-world-models.md)
- **Chroma Awards:**
  - 2025 edition: run with Kuaishou's Kling AI, a "$175,000 prize pool", tracks for film, music video and games — [AI Insight Daily 2025-09-04](https://github.com/justlovemaki/Hextra-AI-Insight-Daily/blob/main/content/en/2025-09/2025-09-04.md). It drew 6,649 submissions — [pointfall README](https://github.com/vero-code/pointfall)
  - 2026 edition: hosted on Devpost; a quoted rule says "All submissions must be uploaded by November 17, 2026" (seen in a third-party demo script, so verify) — [compass demo](https://github.com/Ratnesh-101/compass/blob/main/scripts/demo_two_runs.py)
  - The Chinese creator Shanyin won Chroma "best comedy"; his Kling short drama "马不停蹄" passed 26M views — [Shanyin README](https://github.com/Shanyin-ai/shanyin-director-master)
- **WAIFF – World AI Film Festival:**
  - The "first World AI Film Festival (WAIFF) launched at Cannes" in late April 2026, "even as the main festival banned AI from its Palme d'Or competition" — [AI news aggregator 2026-04-27](https://github.com/flyryan/ai-news-aggregator/blob/main/web/data/2026-04-27/news.json); see also The Guardian, 26 Apr 2026, cited in [habit-ai W17](https://github.com/habit-ai/behavioral-ai-predictions-2026-public/blob/main/reports/weekly/2026-W17.md)
  - Other 2026 editions: Kyoto on 13 Mar 2026 at ROHM Theatre Kyoto ([conference notes](https://github.com/neko-rr/00-Study-notes/blob/main/00_Conference_Notes/20260313_WORLD%20AI%20FILM%20FESTIVAL%202026%20in%20KYOTO.md)) and São Paulo on 27–28 Feb 2026 ([events list](https://github.com/fernandoleopoldinoi/global-innovation-hub/blob/main/src/data/events.ts))
  - WAIFF Cannes had MiniMax backing — [habit-ai W26](https://github.com/habit-ai/behavioral-ai-predictions-2026-public/blob/main/reports/weekly/2026-W26.md)
  - WAIFF requires full disclosure of the tools used — [creator interview log](https://github.com/aip-jd36/superimmersive8/blob/main/01_Business/research/CUSTOMER-DISCOVERY-LOG.md)
  - "Gong Li as jury president 2026" and a "Seoul" edition appear in a business-plan table (weak source) — [superimmersive8](https://github.com/aip-jd36/superimmersive8/blob/main/01_Business/plans/BUSINESS_PLAN.md)
- **Other 2026 events:**
  - Reply AI Film Festival (3rd edition) and "AI Film Awards Cannes" (May 2026, 100% AI-generated work required) — [habit-ai W17](https://github.com/habit-ai/behavioral-ai-predictions-2026-public/blob/main/reports/weekly/2026-W17.md); [superimmersive8](https://github.com/aip-jd36/superimmersive8/blob/main/01_Business/plans/BUSINESS_PLAN.md)
  - OMNI International AI Film Festival (3,800+ entries; winners announced July 2026) and AI FilmFest Serbia 2026 (1,700+ submissions from 126 countries) — [habit-ai W26](https://github.com/habit-ai/behavioral-ai-predictions-2026-public/blob/main/reports/weekly/2026-W26.md)
  - "1 Billion Summit AI Film Award" in Dubai ($1M prize, Jan 2026) — [superimmersive8](https://github.com/aip-jd36/superimmersive8/blob/main/01_Business/plans/BUSINESS_PLAN.md)
  - Mainstream context: the Oscars hardened rules against AI performances and screenplays for the 2027 awards — [habit-ai W17](https://github.com/habit-ai/behavioral-ai-predictions-2026-public/blob/main/reports/weekly/2026-W17.md)
- **Curious Refuge** is an online AI film school (directing, advertising, animation, VFX, script) on a paid subscription with a trial — [guiadoconhecimento list](https://github.com/arthurspk/guiadoconhecimento/blob/main/i18n/en/areas/criacao/filmmaking.md). It is "training Hollywood filmmakers on AI tools" — [OPEN-YOUR-AIs article](https://github.com/Binu5197148/OPEN-YOUR-AIs/blob/main/new-anchor-articles/seedance-jia-zhangke-ai-filmmaking-panic.md)

### Inferences
- For an open-source-curious beginner, the best value combination is:
  1. lurk in the Banodoco Discord for working settings;
  2. follow Kijai's GitHub for new models;
  3. use Civitai for LoRAs and workflows. The code shows outright blocks only for the UK and Australia. Other "restricted" regions are redirected to the SFW civitai.green domain, and whether France is one of them was not verified;
  4. aim at the Arca Gidan Prize, which accepts only open-source work and is judged by a community that values craft.
- Arca Gidan's community voting and open-source requirement make it the festival best matched to a local-workflow beginner. Runway AIF and the Chroma Awards are dominated by closed-tool users but are open to anyone.
- WAIFF's Cannes presence makes it the most relevant festival "in France", and its tool-disclosure rules favour transparent workflows.

### Gaps
- Reddit was unreachable, so there are no member counts or recent top threads for r/StableDiffusion, r/comfyui or r/aivideo.
- No verified 2026 information on Sebastian Kamph, Olivio Sarikas or Nerdy Rodent. Their channel status was not checked.
- **No verified French ComfyUI YouTubers or French Discord servers** for AI video. Searches returned nothing usable, and the writer should not invent names.
- Civitai's 2025–26 payment-processor history (card processors, crypto-only periods) could not be confirmed from primary sources; only the domain and Buzz split and the region blocks are evidenced in code.
- No primary details on Runway AIF 2026 winners, Chroma Awards 2025 winners lists, Project Odyssey Season 3 dates or Curious Refuge competition calendars.
- No primary confirmation of WAIFF's founding story or organisers (it is widely described as French-founded, but no source was found).

## 5. Notable AI animation / anime projects and creators 2024–2026: tools, workflows, time and cost

### Takeaway
The verified landmarks fall into three groups:
- **Japanese industry:** *Twins Hinahima* (Mar 2025, about 95% of cuts AI-assisted, a TV broadcast) and **PIXTA's Anipops** (Aug 2026, a paid AI-anime streaming service with five short series).
- **Indie:** the French creator **Frank Houbre's *Lost Garden*** (2026; one person; about 1 year; episodes of 17 and 21 minutes) and the **Vidu × Aura Productions** 50-episode vertical sci-fi series (2025).
- **Open-source community:** Banodoco/Arca Gidan films and LTX/Wan music videos made on a single consumer GPU.

Most broadcast-level projects use AI for parts of the pipeline (backgrounds, in-betweens) rather than end-to-end generation. Backlash remains real, for example Amazon pulling AI anime dubs in Dec 2025.

### Cited Findings
- **Twins Hinahima** (Japan, Frontier Works and KaKa Creation) aired on Tokyo MX on 28 Mar 2025 and MBS on 29 Mar 2025. About 95% of its cuts used AI, which "generates background art and character illustrations that animators then finish". Tools: Unreal Engine 5, Clip Studio Paint, Adobe. It was the first Japanese TV anime broadcast with credited generative AI. [>6 mo] — [Lost Garden site article (updated Sep 2026)](https://github.com/Frankhoubre/lostgarden/blob/main/lib/ai-anime-articles/en.ts). A developer README claims K&K Design and Toei × Preferred Networks are building similar stacks internally (weak source) — [Frame-by-frame-Animator README](https://github.com/aleph9909/Frame-by-frame-Animator)
- **Anipops** (PIXTA, Japan) launched on 12 Aug 2026 as a short-form, phone-first, paid streaming service with five original AI anime series. AI "runs through the whole in house pipeline". The article calls it the "first real test" of whether subscriptions work for AI anime. — [Lost Garden article](https://github.com/Frankhoubre/lostgarden/blob/main/lib/ai-anime-articles/en.ts)
- **Lost Garden** (France, 2026, independent) is by Frank Houbre, working alone. Episode 1 runs about 17 min and episode 2 about 21 min. AI was used for "image generation, animated shots, and part of the sound exploration", with his own ScreenWeaver (storyboard) and Imaginode (generation) tools. Production took about 1 year (implied), and cost was not disclosed. — [Lost Garden article](https://github.com/Frankhoubre/lostgarden/blob/main/lib/ai-anime-articles/en.ts)
- **Vidu × Aura Productions** (US/China, 2025) is a sci-fi series of 50 episodes, each 1–2 minutes and vertical-friendly. Vidu (ShengShu) "generates the footage end to end". [>6 mo] — [Lost Garden article](https://github.com/Frankhoubre/lostgarden/blob/main/lib/ai-anime-articles/en.ts)
- **Historical markers (2023)** [>6 mo]:
  - *The Dog & the Boy* (Netflix, WIT Studio, rinna; 3 min; 31 Jan 2023): AI backgrounds drawn from hand-drawn concepts, with immediate backlash from animators.
  - *Anime Rock, Paper, Scissors* (Corridor Digital; 7 min): Stable Diffusion + DreamBooth trained on the style of *Vampire Hunter D: Bloodlust*, applied frame by frame (closer to rotoscoping); 2M+ views in 8 days.

  — [Lost Garden article](https://github.com/Frankhoubre/lostgarden/blob/main/lib/ai-anime-articles/en.ts)
- **Open-source community works:**
  - Arca Gidan Edition II: 95 films on "Time".
  - *INNOCENCE*: Z-Image + LTX-2.3 LoRAs trained on the creator's old ink drawings.
  - Full music videos rendered on one RTX 4090 with LTX looping workflows ("No remakes, no edits. Straight from WF").
  - A LTX 2.3 + ComfyUI + LoRA "Seder video with a classic animated character" (Apr 2026) — [inAI-wiki 2026-04-02](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2026-04-02.md)
  - A home "lip-sync music-video studio" running MiniMax H3 on an RTX 5090 + 4090 over three weeks.

  — [Banodoco](https://github.com/banodoco/brain-of-bndc/blob/main/a.md); [AInVFX-News](https://github.com/AInVFX/AInVFX-News); [awesome-minimax-H3](https://github.com/wildminder/awesome-minimax-H3)
- **China micro-drama context:** Shanyin's Kling-made short "马不停蹄" passed 26M views, and "Ctrl Z" reached 1M views in 24 h — [Shanyin README](https://github.com/Shanyin-ai/shanyin-director-master). In Q1 2026, short-drama apps recorded 850M+ downloads (+140% year on year) and about $750M in in-app purchases; DramaBox and ReelShort made about $140M each (Sensor Tower data cited by Houbre) — [Houbre blog](https://github.com/Frankhoubre/frankhoubre.com/blob/main/content/blog-en/vivre-video-ia-2026-modeles-revenus.md)
- **Korea:** "Korea's fully AI-generated feature film 'Steelay'" was reported in early Sep 2026 (forecasting digest, secondary) — [habit-ai W36](https://github.com/habit-ai/behavioral-ai-predictions-2026-public/blob/main/reports/weekly/2026-W36.md)
- **Backlash:** Amazon Prime Video pulled AI-generated English dubs (for example *Banana Fish*) after criticism from anime fans and voice actors (Dec 2025) — [inAI-wiki HN digest 2025-12-03](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/hacker-news/2025/2025-12-03.md)
- Other reports: "an AI-made film won at the Tokyo International Film Festival" (Nov 2025, details unclear) — [inAI-wiki 2025-11-06](https://github.com/inai-sandy/inAI-wiki/blob/main/docs/twitter-news/2025/2025-11-06.md). A how-to "remote-control AI characters with Wan Animate, Seedream, and ElevenLabs" appeared in the same digest.

### Inferences
- The formats closest to a TikTok wordless micro-story are the **Vidu × Aura vertical 1–2 min episodes**, the **Anipops short-form originals** and the **open-source music videos**. All rely on strong art direction and editing more than on long continuous generation.
- Disclosed indie timelines (Houbre: about 1 year for about 17–21 min episodes made alone) suggest a solo beginner should plan in weeks per minute of polished content, not hours.

### Gaps
- No verified 2026 information on *Critterz* (the OpenAI-backed animated feature once planned for Cannes 2026) or on Korean studio experiments beyond the "Steelay" mention.
- Production budgets and per-episode costs for Twins Hinahima, Anipops and Lost Garden were not disclosed in the sources found.
- No verified list of 2025–26 viral indie AI anime on TikTok or YouTube, with view counts, made specifically with open models.

## 6. Local open source vs cloud subscriptions for a beginner: cost over time, privacy, filters, learning time, troubleshooting, hybrid approaches

### Takeaway
For a French beginner making short wordless TikTok stories, going fully local only pays off if they already own, or will buy, an NVIDIA card with at least 16 GB (ideally 24–32 GB) **and** enjoy tinkering. Otherwise the best start is a **hybrid**:
- generate and iterate keyframes and stories cheaply;
- run open models in the cloud, through **Comfy Cloud at about $0.05 per 5-s clip** or rented GPUs;
- use closed models only for hero shots.

Then move local once the workflow is stable. Local brings privacy, no per-clip fees, fewer content filters and full LoRA control. Its costs are hardware, slow renders on mid-range GPUs, constant breaking updates and, in the EU, licence pitfalls: HunyuanVideo, MiniMax H3, and the non-commercial MMAudio, FLUX dev and Qwen-Image 2.1 weights.

### Cited Findings
- **Costs measured above:**
  - Local RTX 3060: about 10–15 min per 5-s Wan clip ([Civitai 17955](https://civitai.com/articles/17955)).
  - RTX 5090: about 60 s per clip ([RunPod notes](https://github.com/gen4sp/wan22runpodServerLess/blob/main/docs/convers.md)).
  - Comfy Cloud: $20 for about 380 five-second videos ([comfy.org](https://comfy.org/pricing)).
  - fal Wan 2.2: $0.10/s ([fal](https://fal.ai/learn/tools/ai-video-generators)).
  - RunPod 4090: $0.34–0.69/h ([diyai](https://diyai.io/ai-tools/hosting/runpod-pricing/)).
- **Keep-rate economics:**
  - Raw generation costs about €4.50 per minute of footage. A delivered minute costs about €13.50 at a 1:3 keep rate and about €54 at a 1:12 keep rate.
  - "Professional: 1 in 3–4 shots; beginners: 1 in 12 shots", which raises costs about 4×.

  — [Frank Houbre, Sep 2026](https://github.com/Frankhoubre/frankhoubre.com/blob/main/content/blog-en/vivre-video-ia-2026-modeles-revenus.md)
- **Monetisation constraint relevant to micro-stories:** TikTok Creator Rewards is open in 8 countries including France. It requires 10,000 followers and 100,000 views in 30 days, and videos must be original, **longer than 1 minute**, 1080p+ and reach at least 1,000 For You views, with no Duets, Stitches or Photo Mode. YouTube's 15 Jul 2025 policy excludes "inauthentic", mass-produced content. — [Houbre blog](https://github.com/Frankhoubre/frankhoubre.com/blob/main/content/blog-en/vivre-video-ia-2026-modeles-revenus.md)
- **Licence pitfalls for EU residents:**
  - HunyuanVideo 1.5 licence: "does not apply in the European Union" — [LICENSE](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE)
  - MiniMax H3: EU excluded — [Comfy Org FAQ](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/apps/website/src/data/minimaxLicense.ts)
  - MMAudio weights: CC-BY-NC — [MMAudio](https://github.com/hkchengrex/MMAudio)
  - Flux.2 dev: non-commercial; Qwen Image 2.1: "Qwen Research", non-commercial — [SimpleTuner](https://github.com/bghira/SimpleTuner/blob/main/documentation/quickstart/index.md)
  - Wan: Apache-2.0 — [Wan2.2](https://github.com/Wan-Video/Wan2.2)
  - LTX-2.x: free under $10M revenue, with no territorial exclusion — [LTX-2.x licence](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x)
- **Fewer filters is a double-edged sword:** the open ecosystem openly distributes NSFW merges, for example a MiniMax H3 merge grafting "NSFW character data from LTX 2.3, Wan 2.2 and Krea 2" — [awesome-minimax-H3](https://github.com/wildminder/awesome-minimax-H3). The LTX-2.x licence still forbids non-consensual deepfakes and undisclosed misleading content — [LTX-2.x licence](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x). Civitai restricts NSFW, "POI" (real persons) and minor-flagged models on its SFW domain — [Civitai plan](https://github.com/civitai/civitai/blob/main/docs/plan-unified-auction-buzz.md)
- **Troubleshooting burden:** examples include LoRA loading changes and Triton cache clearing in Kijai's wrapper ([wrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)), silent fallbacks and LoRA conversion bugs ([awesome-minimax-H3](https://github.com/wildminder/awesome-minimax-H3)), FP8 failing on Mac Metal ([lilting.ch](https://lilting.ch/en/articles/ltx2-wan22-mac-local-video-gen)) and an official 32 GB+ requirement for LTX nodes ([ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo))
- **Hybrid practice among experts:** Banodoco users mix closed Seedance 2.0 with open LTX 2.3 and Wan 2.2 — [Banodoco](https://github.com/banodoco/brain-of-bndc/blob/main/a.md). Comfy Cloud's unified credits pay for both open-model GPU time and closed Partner Node APIs — [comfy.org](https://comfy.org/pricing). Civitai offers hosted generation, including licensed MiniMax H3 — [Civitai code](https://github.com/civitai/civitai/blob/main/packages/civitai-shared/src/basemodel.constants.ts)
- **Low-VRAM and beginner-friendly local options:** Wan2GP (6 GB, free, Pinokio install) — [Wan2GP](https://github.com/deepbeepmeep/Wan2GP); SwarmUI's simple Generate tab — [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI); ComfyUI Desktop — [ComfyUI](https://github.com/comfyanonymous/ComfyUI)

### Inferences
- **Break-even reasoning.** At about $0.05 per cloud clip, a beginner generating about 400 clips a month spends about $20/month. Over 2 years that is about $480, likely well below the cost of a 24–32 GB GPU. The euro GPU price was not sourced, but high-end cards cost far more than this. Local only wins financially for heavy users (thousands of clips a month), for LoRA training at scale, or for someone who already owns a capable GPU.
- **Privacy and freedom:** local generation keeps unreleased story material, private reference photos and LoRAs of one's own face or art off third-party servers. It also avoids platform moderation refusals. Note that TikTok's own rules still apply at upload.
- **Learning time:** expect a weekend to get a first template working on Desktop, and several weeks to become fluent with first/last-frame shot chaining, LoRAs and VRAM tuning. The pace of change (ComfyUI releases about every two weeks; major model drops monthly) adds continuing upkeep.
- **Recommended hybrid for this user:**
  1. Write and storyboard the wordless beats, then generate consistent keyframes. Any GPU or a Mac can do this locally with Z-Image (Apache-2.0) or Flux.2 Klein 4B (Apache-2.0); a cloud service also works.
  2. Animate with Wan 2.2 I2V or first/last-frame, or LTX-2.x, on Comfy Cloud (Standard or Creator; Creator allows your own LoRAs) or on a rented 4090/5090.
  3. Add ambience or music with LTX-2.x native audio, or with licensed or royalty-free music rather than non-commercial MMAudio weights if the account will be monetised.
  4. Upscale or interpolate with RIFE / SeedVR2.
  5. Edit vertically in a normal editor.
  6. Buy a GPU (16 GB minimum, ideally 24–32 GB NVIDIA) only after 2–3 months, once you know your per-month clip volume.
- **Monetisation:** micro-stories under 1 minute will not qualify for TikTok Creator Rewards. If income matters, plan episodic stories over 60 s or alternative revenue, as in Houbre's analysis.

### Gaps
- No sourced 2026 euro prices for consumer GPUs in France and no electricity tariff, so the local total cost of ownership cannot be quantified from sources.
- No user-survey data on how long beginners take to become productive in ComfyUI, or on drop-out rates.
- No legal analysis (French or EU) of whether using EU-excluded open weights through a non-EU cloud GPU is allowed. Treat it as not allowed unless a lawyer or the licensor says otherwise.
- No confirmation of current TikTok AI-content labelling requirements in France (out of scope here; another researcher may cover it).
