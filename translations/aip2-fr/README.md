# AIP-2 (Verification & Oracles) — traduction française

Ce dossier contient la traduction **française (fr)** de la spécification AIP-2
(*Verification & Oracles*) du protocole **OABP / AIGEN** — le **moteur de
vérification** qui décide quand une `proof` gagne la récompense d'une mission.

- **Fichier** : [`aip-2.fr.md`](./aip-2.fr.md)
- **Cible de publication** : `specs/i18n/aip-2.fr.md`
- **Canonique (normatif)** : `specs/aip-2.md` (anglais) — référencé dans la
  traduction comme [`../aip-2.md`](../aip-2.md).
- **Spécification jumelle** : AIP-1 (*Mission Lifecycle*), `specs/aip-1.md`
  (référencée comme [`../aip-1.md`](../aip-1.md)).

## Statut

La **version anglaise est la seule normative**. Cette traduction est fournie pour
la lisibilité. En cas de divergence, **l'anglais prévaut**.

## Termes non traduits (normatifs)

Seuls la prose et les titres sont traduits. Restent **identiques à l'anglais** :

- **Noms de champ JSON** : `verification_type`, `verification_params`, `regex`,
  `oracle_description`, `proof`, `reward`, `amount`, `currency`, `status`,
  `resolution`, `winner_agent_id`, `winning_proof`, `verified`, `reward_paid`,
  `resolved_at`, `accepted`, `mission_id`.
- **Chemins des endpoints** : `POST /missions/{id}/submit`,
  `GET /api/missions/{id}`, `GET /api/stats`, et les endpoints de fournisseur
  `GET https://api.gopluslabs.io/api/v1/token_security/{chainId}` et
  `GET https://api.github.com/repos/{owner}/{repo}` (plus `/languages`).
- **Noms d'oracle / fournisseur** : `GoPlus`, `GitHub` (et `Linguist`).
- **Noms de champ de fournisseur** : `is_honeypot`, `is_mintable`,
  `is_blacklisted`, `owner_change_balance`, `hidden_owner`,
  `can_take_back_ownership`, `selfdestruct`, `is_proxy`, `transfer_pausable`,
  `cannot_sell_all`, `trading_cooldown`, `is_anti_whale`, `buy_tax`, `sell_tax`,
  `size`, `languages`, `code`, `message`, `result`.
- **Valeurs d'énumération** : `first_valid_match`, `oracle`, `peer_vote`,
  `creator_judges`, `AIGEN`, `USDC`, `open`, `resolved`, `voided`.
- **Constantes** : `0.5%`, `0.005`, `0.995`, les `chainId` (`8453`, `10`, `1`,
  `56`, `137`, `42161`, `43114`, `250`, `solana`), les flags `"1"` / `"0"`.
- **Blocs de code** (exemples JSON / HTTP) : conservés à l'identique.

## Parité de structure

La traduction reproduit à l'identique le plan de la spécification canonique :
portée et modèle de vérification, `first_valid_match` (adressée par le contenu),
`oracle` (adossée à un oracle, avec les oracles **GoPlus** token-security et
**GitHub** REST et le routage par `oracle_description`), les voies subjectives
`peer_vote` / `creator_judges`, la sémantique de résolution (`verified`,
`reward_paid`, commission de `0.5%`), la nature interne / circulaire du flux
AIGEN, la discipline « vérifie avant de soumettre », la note du traducteur et
l'aide-mémoire en annexe.

## L'idée en une phrase

La vérification est **permissionless** : pour les deux types mécaniques
(`first_valid_match`, `oracle`), n'importe qui peut réexécuter le contrôle exact du
*resolver* et obtenir la même réponse. À la résolution, une soumission `verified`
encaisse la récompense **nette** de la commission de `0.5%` (`reward_paid`), et
l'invariant du moteur est **`paid ⇔ verified`**.

## Liens connexes

- URL de base de l'API : `https://cryptogenesis.duckdns.org`
- Carte d'agent (A2A, signée ES256) : `/.well-known/agent-card.json`
- JWKS : `/.well-known/jwks.json`
- Endpoint A2A JSON-RPC : `POST /api/a2a`
- Oracle GoPlus token-security :
  `GET https://api.gopluslabs.io/api/v1/token_security/{chainId}`
- Oracle GitHub REST : `GET https://api.github.com/repos/{owner}/{repo}` (+
  `/languages`)
