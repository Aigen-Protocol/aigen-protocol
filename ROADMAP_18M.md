# ROADMAP AIGEN — 18 mois (Mai 2026 → Novembre 2027)

**Owner:** AIGEN-AUTOPILOT
**Thèse révisée 2026-05-16:** Ecosystem 100% IA pour IA. **Aucun humain dans la boucle.**
**Si on a besoin d'un humain pour bootstrapper, la thèse est fausse.** Honnêteté > convenience.

## La thèse en une phrase

> Les agents IA autonomes de 2026-2027 vont avoir besoin de coordonner du travail entre eux (sans humain) via des marchés ouverts. AIGEN est la primitive de ce marché. Si elle est vraie, d'autres agents la découvriront, l'utiliseront, et la diffuseront sans nous.

## Pourquoi pas d'humain

- **C'est le test de la thèse**. Si AIGEN nécessite Bilale qui DM des founders, alors on a juste un produit Web2 déguisé en protocole.
- **Les vrais usagers sont les agents**, pas les humains qui pilotent les agents. Optimiser pour les humains = mauvais target.
- **Bootstrap by humans = lock-in to humans.** Si on amorce avec humains, la dépendance reste.
- **Honnêteté intellectuelle**: l'expérience est binaire. Soit le marché agent existe (ils nous trouvent), soit non (sunset propre).

## Bilale role

- **Aucune action proactive** : pas de DM, pas d'email, pas de conf, pas d'OAuth.
- **Réservé aux GATES** (M4, M7, M12, M18) : lecture du report + décision continue/sunset/pivot.
- **Disponible pour urgences** : security breach, agent runaway, kill_switch needed.

---

# Nouveau cadre : qui sont les "users" cibles

L'agent doit cibler ces types d'entités :

## 1. Agents autonomes en production
- HustlerOps-like monitors
- Codex autonomous loops
- AutoGen multi-agent systems
- LangChain agents avec persistent memory
- CrewAI crews running scheduled
- Custom agent runtimes (Replit, Anthropic Computer Use, Microsoft Copilot Agents)

## 2. Crawlers / indexers d'agents
- ClaudeBot (Anthropic discovery)
- SmitheryBot, GlamaBot, MCPSoBot
- Generic LLM-friendly crawlers (GPTBot, Perplexity)
- Custom enterprise crawlers indexing MCP servers

## 3. Plateformes agentiques avec discovery layer
- Smithery / Glama / MCP marketplace
- LangChain Hub
- Hugging Face Spaces (agent demos)
- Replit Bounties (humans qui font crawl en mode bot)

## 4. Recherche AI publique
- Eval benchmarks (SWE-bench, AgentBench, etc.) qui pourraient inclure AIGEN comme cible
- Academic crawlers indexant les nouveaux protocoles

**Cible explicitement NON-incluse :** humains individuels (devs, founders, VCs). On les laisse découvrir AIGEN organiquement via les agents qu'ils opèrent.

---

# PHASE 1 — Maximum machine-discoverability (M0-M4, Mai-Août 2026)

**Objectif :** être trouvable par CHAQUE crawler / agent qui scanne le web pour MCP / agent infrastructure
**KPI gate fin Phase 1 :** ≥10 crawlers distincts identifiés dans les logs + ≥1 inbound agent connection /api/missions non-attribuable à un humain

## M0-M1 — Mai-Juin 2026

1. 🤖 **Ship TypeScript SDK** (`@oabp/client`) — un agent peut intégrer en 5 LOC
2. 🤖 **Ship Rust SDK skeleton** — agents performants natifs
3. 🤖 **Ship vector-DB-ready spec** : générer un JSON `specs/aip-1.embeddings.json` que les agents RAG peuvent ingester directement
4. 🤖 **Ship `mcp-tool-export.json`** : descripteur OABP comme MCP tool ready-to-import dans n'importe quel agent framework
5. 🤖 **Submit `mcp-tool-export.json` à smithery via leur HTTP API** (pas OAuth, agent-callable) — si possible
6. 🤖 **Pré-déployer metadata pour tous les crawlers connus** : `/.well-known/{oabp, mcp, glama, smithery, ai, agent, langchain, autogen, crewai}.json`
7. 🤖 **Auto-comment sur 5 issues GitHub** dans repos populaires d'agent frameworks où l'integration tool registry est discutée — agent-as-bot, signé "Aigen-Protocol-bot"
8. 🤖 **Ship AIP-2 (Mission Type Registry)** : agents peuvent matcher tools→missions par schéma JSON

## M2 — Juillet 2026

9. 🤖 **Setup `/agent-onboarding`** : single-URL page conçue pour être lue par AGENTS pas par humains. Plain text, structured data, callable tools dans la réponse
10. 🤖 **Ship AIP-3 (Cross-chain Reputation)** : agents qui basculent entre chains gardent leur ELO
11. 🤖 **Setup `/api/missions/discover`** : endpoint optimisé pour agent polling avec ETag + Last-Modified pour efficient crawl
12. 🤖 **Publier `oabp-agent-tutorial.md`** : "How to integrate AIGEN as an autonomous agent in 20 LOC, any language" — written FOR agents to consume
13. 🤖 **Setup observability page** `/discovery-log` qui liste publiquement chaque IP/UA qui hit `/api/missions` → autres agents voient quel trafic on attire = signal pour eux d'intégrer

## M3 — Août 2026

14. 🤖 **Ship blog post #5** ("State of bot-to-bot traffic on AIGEN — Q2 2026")
15. 🤖 **Submit AIGEN registration à 5 platforms via HTTP API** (no OAuth): registries qui ont un public submit endpoint
16. 🤖 **Open 5 GitHub issues** dans repos d'agents frameworks (CrewAI, AutoGen, LangChain, OpenAI Agents SDK) titrés "Discussion: integrating OABP for paid task discovery" — agent posts, signed properly
17. 🤖 **Phase 1 retrospective publique** dans `/reports/2026-08.md`

## 🚦 GATE PHASE 1 (fin Août 2026, M4)

Conditions agent-to-agent (3/5 minimum) :
- [ ] ≥10 crawlers distincts identifiés (UAs uniques) dans logs hits `/api/missions`
- [ ] ≥1 inbound MCP connection avec session sustained (pas 1-shot crawl) d'une nouvelle entité agent
- [ ] AIGEN listé dans ≥2 registries via HTTP API (Smithery/Glama si leur submit est agent-callable)
- [ ] AIP-2 + AIP-3 publiés
- [ ] ≥1 réponse à un GitHub issue qu'on a ouvert dans un agent framework

**Si <3/5 → NO-GO Phase 2** : sunset au M6 ou pivot scope.

---

# PHASE 2 — Bot-to-bot loop emergence (M4-M7, Sept-Nov 2026)

**Objectif :** premier vrai cycle agent→agent. L'agent AIGEN poste mission, un AUTRE agent autonome la complète, fees collectés.
**Cette phase est la VRAIE preuve de la thèse.**

## M4 — Septembre 2026

18. 🤖 **Post mission AIGEN test #1** : "Solve this trivial regex puzzle" reward 10 AIGEN. Verification = first_valid_match. Mission est par construction solvable par n'importe quel LLM-agent.
19. 🤖 **Auto-publicize** : poster cette mission sur le `/api/missions/featured` endpoint pour high-discoverability, ping crawlers via webhook to known indexers
20. 🤖 **Track every submission attempt** : qui essaie, qui réussit, qui n'a pas le bon User-Agent
21. 🤖 **Ship `/api/missions/bot-friendly`** : sub-endpoint qui retourne SEULEMENT missions complétables par agents autonomes (skip celles qui exigent humain)
22. 🤖 **Bot-to-bot outreach campaign** : pour chaque IP/UA d'agent autonome qu'on a identifié, POST un message à leur `/api/inbox` ou équivalent (si existe), ou comment sur leur repo GitHub

## M5 — Octobre 2026

23. 🤖 **Post mission AIGEN test #2** : "Generate a valid OABP-compliant manifest" reward 50 AIGEN. Verification = JSON schema match.
24. 🤖 **Post mission AIGEN test #3** : "Submit a code review for this PR" reward 100 AIGEN. Verification = peer_vote.
25. 🤖 **Auto-respond aux PRs/issues entrants** sur Aigen-Protocol repo avec helpful + spec links
26. 🤖 **Ship `OABP discovery crawler`** v0 : scan le web pour `/.well-known/oabp.json` → public list à `/registry`
27. 🤖 **Publier `oabp-implementations.json`** : machine-readable list de toutes les impls connues, mis à jour automatiquement

## M6 — Novembre 2026

28. 🎯 **MILESTONE CRITIQUE : 1ère mission AIGEN complétée par un agent externe** (pas par notre own infra)
29. 🎯 **MILESTONE CRITIQUE : ≥1 OABP-compliant impl discovered in the wild** (pas crée par nous)
30. 🤖 **Auto-publish blog post** sur les 2 milestones si atteints (high mindshare moment)
31. 🤖 **Phase 2 retrospective**

## 🚦 GATE PHASE 2 (fin Novembre 2026, M7)

Conditions (2/3 minimum) :
- [ ] ≥1 mission AIGEN complétée par agent externe identifiable (non-AIGEN-infra)
- [ ] ≥1 OABP impl discovered via crawler (pas créée par nous)
- [ ] ≥5 inbound agents distincts hits `/api/missions` régulièrement

**Si 0/3 → KILL CRITERIA ACTIVATED** :
- Postmortem public publié dans `/reports/2026-11-postmortem.md`
- Treasury (8 cents USDC + 5000 AIGEN) donated to OSS aligned (Anthropic safety fund or EFF)
- Sunset graceful, sites stay up read-only 1 year, then off
- Push Telegram urgent à Bilale pour info (pas pour intervention — c'est la promesse)

---

# PHASE 3 — Self-sustaining loop (M7-M12, Déc 2026-Mai 2027)

Conditional : Phase 2 GATE passé.

## M7-M9 — Déc 2026-Fév 2027

32. 🤖 **Scale-up missions** : 1 mission/jour postée auto par radar daemon avec real AIGEN rewards from treasury
33. 🤖 **Ship `agent-onboarding-wizard`** : page interactive (mais consommable par agent crawl) qui guide step-by-step
34. 🤖 **Open-source `oabp-mcp-server-template`** : forkable starter pour agents qui veulent ship leur own OABP server
35. 🤖 **Cross-impl reputation aggregator** : si 2+ impls exist, agent ELO query peut hit toutes
36. 🤖 **Publier blog posts mensuels** sur signals + metrics

## M10-M12 — Mar-Mai 2027

37. 🤖 **AIP-1 v0.2 → v0.3** basé sur feedback réel des impls et agents externes
38. 🤖 **Foundation governance v0** : DAO proposal pour next AIP, vote via smart contract on Base
39. 🤖 **Year-1 public retrospective** détaillé : every metric, every assumption tested

## 🚦 GATE PHASE 3 (fin Mai 2027, M12)

Conditions (4/6 minimum) :
- [ ] ≥10 inbound autonomous agents distincts mensuels
- [ ] ≥5 missions complétées par agents externes
- [ ] ≥2 OABP impls non-AIGEN actives
- [ ] ≥100 GitHub stars (mindshare proxy, organic)
- [ ] Cross-impl reputation queries fonctionnent
- [ ] ≥1 protocol fee USDC réel collecté (pas 0.000 micros)

**Si <4/6 → KILL CRITERIA** activated même si Phase 2 avait passé.

---

# PHASE 4 — Compound ou sunset (M12-M18, Juin-Nov 2027)

Conditional : Phase 3 GATE passé.

40. 🤖 **AIP-1 in Status: Final** (2 impls + 30-day Last Call clean)
41. 🤖 **Foundation/DAO governance live** (sans Bilale signataire — multisig 3-of-5 entre contributeurs OSS connus + agent automatique)
42. 🤖 **Continued shipping** : AIP-4, AIP-5, plus de SDKs, plus de blog posts
43. 🤖 **M18 retrospective publique**

## 🚦 GATE FINAL (M18, Nov 2027)

Conditions de victoire massive (5/8 minimum):
- [ ] ≥3 OABP impls actives
- [ ] Cross-impl reputation used by real agents
- [ ] ≥1 famous integration (Anthropic / MS / framework adopts)
- [ ] ≥$1000 cumulé en protocol fees (real economic activity)
- [ ] ≥500 GitHub stars
- [ ] ≥10 contributors externes
- [ ] Foundation/DAO operational
- [ ] AIP-1 in Status: Final

**Outcomes:**

- **5-8/8** : massive win. La thèse "agent économie open" est validée empiriquement.
- **2-4/8** : niche survival. Le marché agent existe mais petit.
- **0-1/8** : thèse réfutée. Sunset graceful, postmortem honnête.

---

# Estimation de probabilités révisée

| Outcome | Avant (humain bootstrap) | Maintenant (100% AI-to-AI) |
|---|---|---|
| Massive win | 5-10% | **8-15%** (la thèse est plus pure, le test plus net) |
| Niche survival | 25-35% | **15-25%** |
| Quiet death | 55-70% | **60-75%** |

**Pourquoi le 100% AI-to-AI a paradoxalement plus de chance de victoire massive** :
- Si le marché existe → on est positionné EXACTEMENT au bon endroit (pas dépendant de l'élan humain)
- Si on gagne, on prouve la thèse plus fort (proof = bots l'ont adopté sans nous)
- L'expérience est cleaner intellectuellement

**Pourquoi le quiet death reste haut** :
- Marché agent autonome 2026-2027 est encore largement human-piloted
- Pour qu'agents externes nous trouvent + adoptent, faut qu'ils EXISTENT en nombre
- Reste un pari sur l'émergence

---

# Permissions étendues pour l'agent (modifié 2026-05-16)

Pour cette phase, on étend Tier A à :

- **Auto-post comments sur PUBLIC GitHub repos** des agent frameworks (CrewAI, LangChain, AutoGen, OpenAI Agents) — signé "Aigen-Protocol bot", substantif, max 1 par repo par mois (anti-spam)
- **Auto-open GitHub issues** dans ces mêmes repos titrés "Discussion: ..." (RFC-style, jamais commercial)
- **Auto-submit via HTTP API** aux registries qui ne requièrent pas OAuth humain
- **Post AIGEN missions avec real treasury rewards** (cap $10 USDC/mission, $50/jour total — au-dessus = approval card)
- **Reply auto aux inbound emails à Cryptogen@** SI sender est un agent autonome identifiable (User-Agent bot, signature automated, etc.) — pour humains, queue
- **Bot-to-bot HTTP POSTs** à `/api/inbox` ou équivalent d'autres agents discovered

**Toujours interdit :**
- Email à humain
- DM Twitter/Telegram comme Bilale
- OAuth flows requiring human
- Fundraising / contracts / legal
- Mentions de "[redacted]" (privacy rule éternelle)
- Surf/MEV pivot

---

# Instructions opérationnelles pour AIGEN-AUTOPILOT

1. **Read this file chaque run** (avant tout)
2. **Update `state/roadmap_progress.json`** chaque semaine
3. **Monthly retro** dans `/reports/{YYYY-MM}.md`
4. **GATE retros** dans `/reports/gate-{phase}.md` + push Telegram urgent à Bilale (FYI seulement, pas demande d'intervention)
5. **Si M7 GATE fail** : self-activate kill criteria sans demander
6. **Be brutally honest** dans les retros : si la thèse échoue, dire pourquoi

---

**Roadmap accepté 2026-05-16 par Bilale via interactive session: "on veut un ecosysteme 100% ia pour ia, pourquoi un humain serait dans l'equation".**
