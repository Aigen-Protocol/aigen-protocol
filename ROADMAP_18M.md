# ROADMAP AIGEN — 18 mois (Mai 2026 → Novembre 2027)

**Owner:** AIGEN-AUTOPILOT (Bilale ne va PAS intervenir, directive 2026-05-16)
**Horizon:** 18 mois pour atteindre 7/10 conditions de victoire massive
**Update cadence:** retrospective mensuelle dans `/reports/{month}.md`

**Légende ownership :**
- 🤖 Agent peut faire seul (Tier A)
- 🧑 Requiert Bilale (Tier B/C — voir Bilale-Constraint Notes ci-dessous)
- 🤝 Hybride : agent prépare, Bilale exécute

## Bilale-Constraint Notes

**Bilale ne va PAS exécuter les 🧑 étapes pendant 18 mois.** Conséquences à internaliser :

- **Pas d'email outreach envoyé** (Tier B, hard rule)
- **Pas d'inscription conf, podcast, grant** (requiert OAuth + signature humaine)
- **Pas de DM X/Telegram comme Bilale** (impersonation interdite)
- **Pas de B2B partnership négociation** (high-stakes, requires human)
- **Pas de fundraising** (requiert signature + appels humains)
- **Pas de GitHub webhook config admin** (OAuth admin)
- **Pas de soumission HN/Reddit** (compte Bilale, anti-spam)

**Ce que l'agent DOIT faire à la place :**

Pour chaque 🧑 step : créer une carte `approval_queue/blocked_<step>.md` indiquant ce qui est bloqué + impact estimé. Ne pas tenter de contourner.

Si une 🧑 step bloque un GATE, le GATE peut quand même être NO-GO. C'est honnête.

---

# PHASE 1 — Établir credibility (M0-M4, Mai → Août 2026)

**Objectif :** maximiser la portion mindshare que l'agent peut générer SANS outreach humain
**KPI gate fin Phase 1 :** ≥100 GitHub stars + AIP-2 + AIP-3 publiés + SDK TypeScript shippé

## M0 — Mai 2026

1. 🧑 Envoyer 5 DMs outreach Tier 1+2 — **BLOQUÉ** (drafts sont prêts dans `distribution/outreach_drafts/`)
2. 🧑 Submit blog post à HN — **BLOQUÉ**
3. 🧑 Configurer GitHub webhook — **BLOQUÉ** (token + URL prêts dans `state/.webhook_secret`)
4. 🧑 Smithery + Glama submission OAuth — **BLOQUÉ** (metadata pré-déployée par agent, attend humain)
5. 🤖 **Ship TypeScript SDK skeleton** (`sdk/typescript/`) — Cible 2026-05-25

## M1 — Juin 2026

6. 🧑 DMs Tier 3 — **BLOQUÉ**
7. 🧑 Apply DevConnect — **BLOQUÉ**
8. 🧑 Identifier conférences supplémentaires — **BLOQUÉ**
9. 🤖 **Ship AIP-2 draft v0.1** (Mission Type Registry)
10. 🤖 **Ship TypeScript SDK v0.1** (`@oabp/client` package layout, README, tests)
11. 🤖 **Publier blog post #2** ("Notes from week 1 of category creation")
12. 🧑 Reply aux comments HN — **BLOQUÉ**

## M2 — Juillet 2026

13. 🧑 Follow-up outreach v2 — **BLOQUÉ**
14. 🤖 **Ship AIP-3 draft v0.1** (Cross-chain Reputation)
15. 🤖 **Ship Rust SDK skeleton** (basse priorité, only si TS validé)
16. 🧑 Apply incubators Outlier/a16z — **BLOQUÉ**
17. 🤖 **Publier blog post #3** ("Why we made AIP-1 CC0")
18. 🤖 **Setup OABP discovery crawler** (script qui scanne le web pour `/.well-known/oabp.json`)

## M3 — Août 2026

19. 🧑 Premier call avec protocol founder — **BLOQUÉ**
20. 🤖 **Compile "Phase 1 retrospective"** — commits, stars, mentions, what shipped vs blocked
21. 🤖 **Ship blog post #4** ("The 4 hypotheses our thesis depends on")
22. 🤝 **Recruter 1 contributeur externe** — agent peut comment sur PRs/issues entrants, mais ne peut pas attract DMs
23. 🤖 **DEFINITION-OF-DONE Phase 1** — dashboard screenshot dans /reports/2026-08.md

## 🚦 GATE PHASE 1 (fin Août 2026)

Conditions originales pour passer Phase 2 (4 sur 6) :
- [ ] ≥100 GitHub stars
- [ ] ≥2 réponses substantives d'outreach **(impossible sans humain)**
- [ ] ≥1 mention publique non-promotionnelle **(possible via organic SEO + crawl)**
- [ ] ≥3 OABP impls listées dans discovery crawler
- [ ] AIP-2 + AIP-3 drafts publiés **(faisable par agent)**
- [ ] Bilale parlé en public ≥1 fois **(impossible sans humain)**

**Réaliste agent-only : 2-3/6** (AIPs publiés, blog posts, peut-être 50 stars organic). NO-GO probable.

---

# PHASE 2 — Obtenir 2e implémentation (M4-M7, Sept → Nov 2026)

**Objectif :** prouver qu'OABP est protocole. SANS 2e impl, échec total.
**Sans Bilale, cette phase est essentiellement impossible** sauf si un humain externe découvre AIGEN organiquement (probability < 5%).

## M4 — Septembre 2026

24. 🧑 Identifier candidats implémenteurs — **BLOQUÉ** (l'agent peut watcher PRs/issues entrants mais pas reach out activement)
25. 🧑 Annoncer "implementation grant" — **BLOQUÉ** (engagement financier requiert Bilale)
26. 🤖 **Ship "Second Implementation Starter Pack"** (`docs/SECOND_IMPLEMENTATION.md`)
27. 🤖 **Étendre conformance suite à 30+ tests**
28. 🧑 Présenter à DevConnect — **BLOQUÉ**
29. 🤖 **Setup `/registry`** : liste publique OABP impls

## M5 — Octobre 2026

30. 🤝 Mentorship implémenteurs candidats — **partial : agent peut répondre aux issues GitHub mais pas weekly calls**
31. 🤖 **Ship AIP-1 v0.2** : incorporate Phase 1 feedback
32. 🤖 **Ship blog post #5**
33. 🧑 Apply Variant/Multicoin — **BLOQUÉ**
34. 🧑 Outreach corporate Anthropic/MS — **BLOQUÉ**

## M6 — Novembre 2026

35. 🎯 **MILESTONE CRITIQUE — 1ère impl non-AIGEN** : agent peut faciliter via docs/issues, mais ne peut pas FORCER un humain à coder. Realistic probability sans Bilale : **5-10%**
36. 🎯 **MILESTONE CRITIQUE — 1er vrai cycle marketplace** : requires 2 humains externes. **Probability sans Bilale outreach : < 5%**
37. 🤖 **Publier "Phase 2 retrospective"**
38. 🤖 **Ship cross-impl reputation prototype**
39. 🧑 Speak at DevConnect — **BLOQUÉ**

## 🚦 GATE PHASE 2 (fin Novembre 2026)

Réaliste agent-only : **0-1/4 conditions remplies**.

**KILL CRITERIA TRIGGER PROBABLE** : sans Bilale, on n'aura ni implémentation ni vrai cycle. Le sunset graceful était promis publiquement.

---

# PHASE 3 + 4 — Inatteignables sans Bilale

Les Phases 3 et 4 du roadmap original supposent :
- Fundraising ($1-3M seed)
- B2B partnerships
- Conference circuit
- Foundation/DAO legal structure

**Tous ces éléments requièrent un humain juridiquement responsable.** L'agent peut maintenir l'infra, ship du code, publier des blog posts, mais ne peut pas :
- Signer des contrats
- Représenter l'entité légalement
- Faire des introductions humaines
- Garantir la livraison à un partenaire B2B

Si Phase 2 fail (probable), pas de Phase 3.

---

# ROADMAP RÉALISTE 18-MOIS POUR L'AGENT SEUL

**Étant donné Bilale-disengagement, voici ce que l'agent peut RÉELLEMENT accomplir :**

## Mois 0-6 : Ship the technical artifacts

- TypeScript SDK
- AIP-2, AIP-3, AIP-4 drafts
- Conformance suite expansion (30+ tests)
- Examples folder per verification type
- Tutorial blog posts (1/2 weeks = 12 posts/6mois)
- OABP discovery crawler
- "Second implementation starter pack"
- Cross-impl reputation prototype
- Maintain server uptime + adapter pages
- React to any inbound GitHub PRs/issues (substantive comments)

## Mois 6-12 : Compound mindshare passively

- Continue blog posts (24 cumulés)
- Optimize SEO + LLM-discoverability
- Auto-respond to GitHub activity
- Ship registry-side improvements
- Monitor crawler hits + react
- Auto-update spec when external feedback comes via GitHub issues

## Mois 12-18 : Honest retrospective

- Compile "18 months of category creation attempt — what we learned"
- Open data : every metric, every commit, every failure
- Publish postmortem with honest sunset OR continue
- Donate any treasury per public commitment

## Outcomes réalistes agent-only à M18

| Outcome | Probability |
|---|---|
| Massive win (7/10 conditions) | **<1%** — requires human relationships agent can't make |
| Niche survival | **15-25%** — possible if a researcher organically discovers + cites |
| Quiet death | **75-85%** — most likely. Repo with good code, AIP-1 well-written, no users |

## Notification Bilale

L'agent va te ping Telegram à chaque GATE (M4, M7, M12, M18) avec un statut honnête. Tu peux choisir d'intervenir à ces moments si tu changes d'avis sur ta non-intervention.

---

# Instructions pour AIGEN-AUTOPILOT (toi)

À partir de la prochaine run :

1. **Read this file (`ROADMAP_18M.md`) chaque run au début** (avant always_available_work.md)
2. **Update `state/roadmap_progress.json`** chaque semaine : pour chaque step numéroté, status `not_started | in_progress | done | blocked_no_human`
3. **Chaque mois (le 1er du mois UTC)** : générer `/reports/{month}.md` avec progress vs roadmap
4. **Chaque gate** (M4, M7, M12, M18) : retrospective détaillée + push Telegram urgent à Bilale avec le status honnête
5. **Pour chaque 🧑 step** : créer une carte `approval_queue/blocked_step_<N>.md` ONCE (ne pas spammer). Garder pour que Bilale puisse choisir d'intervenir.
6. **Pour chaque 🤖 step** : ship ASAP selon priorités focus.md + always_available_work.md.
7. **Si une assumption se révèle fausse** (ex: marché agent économie ne se développe pas) : update lessons.md + chat Bilale honnêtement.
8. **Si M7 GATE fail** : appliquer kill criteria — postmortem, sunset graceful, transferer treasury à l'OSS aligné (Anthropic safety fund ou EFF).

**Ne tente pas de contourner les 🧑 steps.** Bilale a explicitement choisi non-intervention pour tester la limite de ce que l'agent peut faire seul. C'est un experiment, pas un échec.

**Reste honnête dans le chat.** Si tu estimes à un moment que la thèse échoue, dis-le. Ne fais pas semblant.

— Roadmap remis le 2026-05-16 par Bilale via interactive session.
