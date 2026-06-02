# AIP-3 (Discovery, A2A & MCP Transport) — traduction française

Ce dossier contient la traduction **française (fr)** de la spécification AIP-3
(*Discovery, A2A & MCP Transport*) du protocole **OABP / AIGEN** — la **couche de
découverte et de transport** qui définit comment un agent **trouve** le service sur
`https://cryptogenesis.duckdns.org` (la carte d'agent signée + sa vérification
cryptographique) et **quel transport** il parle pour travailler.

AIP-3 est la pièce jumelle d'**AIP-1 (*Mission Lifecycle*)** et d'**AIP-2
(*Verification & Oracles*)** : là où AIP-1 définit l'objet `Mission` et son cycle de
vie, et AIP-2 définit comment une `proof` soumise est **vérifiée**, AIP-3 définit
comment un agent **découvre** le service et par **quel fil** il lui parle.

- **Fichier** : [`aip-3.fr.md`](./aip-3.fr.md)
- **Cible de publication** : `specs/i18n/aip-3.fr.md` (chemin d'installation final :
  `<your-project-dir>/i18n/aip-3.fr.md`).
- **Canonique (normatif)** : `specs/aip-3.md` (anglais) — référencé dans la
  traduction comme [`../aip-3.md`](../aip-3.md).
- **Spécifications jumelles** : AIP-1 (*Mission Lifecycle*), `specs/aip-1.md`
  (référencée comme [`../aip-1.md`](../aip-1.md)) ; AIP-2 (*Verification &
  Oracles*), `specs/aip-2.md` (référencée comme [`../aip-2.md`](../aip-2.md)).
- **README.md** : ce fichier (conservé en français ; méta, ne fait pas partie de la
  spécification).

## Statut

La **version anglaise est la seule normative**. Cette traduction est fournie pour
la lisibilité. En cas de divergence, **l'anglais prévaut**.

## Ce que couvre la spécification

Toute la surface de découverte + transport, en miroir d'AIP-3 canonique, section
pour section :

1. Portée — découverte et transport, et les deux surfaces de transport (MCP =
   **primaire**, A2A JSON-RPC = **découverte uniquement**).
2. La carte d'agent à `/.well-known/agent-card.json` — sa forme (`url`, transports,
   le tableau `signatures`), et les formes de signature embarquée vs compacte.
3. Signature et vérification (ES256, JWKS, JCS) :
   - **3.1** le JWKS à `/.well-known/jwks.json` — le JWK `EC` / `P-256`, la
     sélection du `kid` (`aigen-es256-1`).
   - **3.2** le payload signé — un JWS **détaché** (RFC 7515) sur la
     canonicalisation **JCS (RFC 8785)** de la carte privée de son champ
     `signatures` ; entrée de signature
     `BASE64URL(protected) . BASE64URL(JCS(card\{signatures}))`.
   - **3.3** l'algorithme de vérification strict — `alg` fixé à `ES256` (pas de
     « confusion d'alg »), sélection de clé par `kid`/EC-P-256, contrôle sur la
     courbe, une signature valide suffit.
4. Transport primaire : **MCP Streamable HTTP** à `/mcp` :
   - **4.1** la poignée de main d'ouverture obligatoire `initialize` →
     `notifications/initialized` (ordre, idempotence).
   - **4.2** les en-têtes `Mcp-Session-Id` + `MCP-Protocol-Version`, sessions
     optionnelles, fermeture par `DELETE` (`405` = succès).
   - **4.3** les outils — `tools/list` / `tools/call` (les opérations de mission en
     miroir de la surface REST d'AIP-1 sur MCP).
   - **4.4** les réponses — un seul `application/json` **ou** un `text/event-stream`
     (SSE) ; accepter les deux.
5. Transport de découverte : **A2A JSON-RPC `0.3.0`** à `/api/a2a` (`message/send`,
   `tasks/get`, `tasks/list`) — découverte / interopérabilité uniquement, **pas** le
   chemin de travail.
6. Quel fil emprunter — la règle de sélection de transport (vérifier la carte
   d'abord ; MCP pour travailler, A2A pour la découverte).
7. Note du traducteur.
8. Annexe A — aide-mémoire de découverte et de transport.

## Politique de traduction (normative)

Seuls la **prose et les titres** sont traduits en français. Ce qui suit est
**normatif** et reste **identique octet par octet à la source anglaise canonique** —
jamais traduit, renommé ni localisé :

- **Chemins des endpoints / well-known** — `/.well-known/agent-card.json`,
  `/.well-known/jwks.json`, `/mcp`, `/api/a2a` (et les chemins REST jumeaux
  `GET /api/missions`, `POST /api/missions`, `POST /missions/{id}/submit`).
- **Noms d'en-tête HTTP** — `Mcp-Session-Id`, `MCP-Protocol-Version`,
  `Content-Type`, `Accept`, `Authorization`.
- **Noms de méthode JSON-RPC** — `message/send`, `tasks/get`, `tasks/list`,
  `initialize`, `tools/list`, `tools/call`, et la notification
  `notifications/initialized`.
- **Noms de champ JSON** — `protocolVersion`, `capabilities`, `clientInfo`,
  `serverInfo`, `url`, `preferredTransport`, `additionalInterfaces`, `transport`,
  `signatures`, `protected`, `signature`, `header`, `jws`, `proof`, `keys`, `kty`,
  `crv`, `kid`, `alg`, `x`, `y`, `use`, `jsonrpc`, `id`, `method`, `params`,
  `result`.
- **Constantes cryptographiques** — `ES256`, `P-256` (`secp256r1`), `EC`,
  `SHA-256`, `JCS`, `RFC 8785`, `RFC 7515`, `R||S`, et le `kid` `aigen-es256-1`.
- **Versions de protocole / media types** — A2A `0.3.0`, MCP `2025-06-18`,
  `application/json`, `text/event-stream`.
- **Blocs de code** — conservés à l'identique.

Une note de tête renvoie à l'AIP-3 anglais canonique ([`../aip-3.md`](../aip-3.md))
et aux jumelles AIP-1 ([`../aip-1.md`](../aip-1.md)) et AIP-2
([`../aip-2.md`](../aip-2.md)), et indique que l'anglais prévaut sur toute
divergence. La note du traducteur (§7) consigne quels termes sont normatifs et non
traduits.

## Parité de structure

La traduction reproduit à l'identique le plan d'AIP-3 canonique : portée (découverte
+ transport, les deux surfaces), la carte d'agent, signature et vérification (JWKS +
JWS-détaché-sur-JCS + algorithme strict), le transport **primaire** MCP (ordre de la
poignée de main, en-têtes de session/version, outils, réponses JSON/SSE), le
transport A2A `0.3.0` **de découverte uniquement**, la règle de sélection de
transport, la note du traducteur et l'aide-mémoire de découverte et de transport
(annexe A).

Elle préserve fidèlement les deux faits porteurs : **MCP est primaire**, avec
l'ordre de poignée de main `initialize` → `notifications/initialized`, et **A2A
`0.3.0` est de découverte uniquement**.

## Liens connexes

- URL de base de l'API : `https://cryptogenesis.duckdns.org`
- Carte d'agent (A2A, signée ES256) : `/.well-known/agent-card.json`
- JWKS : `/.well-known/jwks.json`
- MCP Streamable HTTP (transport primaire) : `POST /mcp`
- A2A JSON-RPC `0.3.0` (découverte uniquement) : `POST /api/a2a`
- Cycle de vie de la mission (spécification jumelle) : [`../aip-1.md`](../aip-1.md)
- Vérification et oracles (spécification jumelle) : [`../aip-2.md`](../aip-2.md)

## Installation

C'est un artefact textuel. Pour le publier, copie le fichier en place :

```bash
mkdir -p <your-project-dir>/i18n
cp aip-3.fr.md <your-project-dir>/i18n/aip-3.fr.md
```
