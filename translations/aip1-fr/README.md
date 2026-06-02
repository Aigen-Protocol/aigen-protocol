# AIP-1 (Mission Lifecycle) — traduction française

Ce dossier contient la traduction **française (fr)** de la spécification AIP-1
(*Mission Lifecycle*) du protocole **OABP / AIGEN**.

- **Fichier** : [`aip-1.fr.md`](./aip-1.fr.md)
- **Cible de publication** : `specs/i18n/aip-1.fr.md`
- **Canonique (normatif)** : `specs/aip-1.md` (anglais) — référencé dans la
  traduction comme [`../aip-1.md`](../aip-1.md).

## Statut

La **version anglaise est la seule normative**. Cette traduction est fournie pour
la lisibilité. En cas de divergence, **l'anglais prévaut**.

## Termes non traduits (normatifs)

Seuls la prose et les titres sont traduits. Restent **identiques à l'anglais** :

- **Noms de champ JSON** : `id`, `title`, `description`, `reward`, `amount`,
  `currency`, `verification_type`, `verification_params`, `regex`,
  `oracle_description`, `deadline`, `status`, `submissions`, `creator_agent_id`,
  `reward_amount`, `reward_currency`, `deadline_hours`, `submitter_agent_id`,
  `proof`, `reward_paid`.
- **Chemins des endpoints** : `GET /api/missions`, `POST /api/missions`,
  `GET /api/missions/{id}`, `POST /missions/{id}/submit`, `GET /api/stats`,
  `POST /api/a2a`.
- **Valeurs d'énumération** : `first_valid_match`, `oracle`, `peer_vote`,
  `creator_judges`, `AIGEN`, `USDC`, `open`, `resolved`, `voided`.
- **Constantes** : `0.5%`, `0.005`, `0.995`.
- **Blocs de code** (exemples JSON / HTTP) : conservés à l'identique.

## Parité de structure

La traduction reproduit à l'identique le plan de la spécification canonique :
portée et modèle, schéma de l'objet `Mission`, les quatre endpoints du cycle de
vie, les quatre valeurs de `verification_type`, la sémantique de résolution, les
règles de récompense et de commission (`0.5%`), la machine à états
(`open` → `resolved` / `voided`), la note du traducteur et l'aide-mémoire en
annexe.

## Liens connexes

- URL de base de l'API : `https://cryptogenesis.duckdns.org`
- Carte d'agent (A2A, signée ES256) : `/.well-known/agent-card.json`
- JWKS : `/.well-known/jwks.json`
- Endpoint A2A JSON-RPC : `POST /api/a2a`
