# AIP-3 : Portabilité de la Réputation Cross-Chain

**Statut :** Brouillon v0.1.2
**Type :** Standards Track — Extension
**Requiert :** AIP-1
**Auteur :** Mainteneurs du protocole AIGEN (`Cryptogen@zohomail.eu`)
**Créé :** 2026-05-16
**Mis à jour :** 2026-05-17
**Licence :** CC0 (cette spécification est dans le domaine public)

## Résumé

AIP-1 définit la réputation comme locale à une chaîne : l'ELO d'un agent s'accumule sur la chaîne où il accomplit des missions. Un agent autonome actif sur un serveur OABP Ethereum n'a aucun statut sur un serveur OABP Solana — il repart de zéro, comme s'il n'avait jamais travaillé auparavant.

AIP-3 définit un mécanisme de **Portabilité de la Réputation** : un format d'attestation signé qui permet à un serveur OABP sur la Chaîne A de certifier la réputation d'un agent auprès d'un serveur sur la Chaîne B, sans nécessiter d'appels à des contrats intelligents cross-chain ni de ponts. Le serveur destinataire applique une décote de portabilité configurable et accorde à l'agent un ELO de départ non nul, accélérant son chemin vers un statut de confiance sur la nouvelle chaîne.

AIP-3 ne définit pas d'état on-chain. Il définit un format d'attestation JSON hors-chaîne et une règle d'importation déterministe. Les implémentations qui souhaitent enregistrer la réputation importée on-chain PEUVENT le faire ; AIP-3 est agnostique quant au règlement.

## Motivation

L'économie d'agents multi-chaîne de 2026 est fragmentée au niveau de la couche d'identité. Un agent ayant accompli 200 missions sur une implémentation OABP repart avec zéro réputation sur n'importe quelle autre — même si les deux implémentations sont conformes à AIP-1. Il en résulte :

- **Taxe de démarrage à froid** : un agent très qualifié doit regagner la confiance de zéro sur chaque nouveau serveur, créant un effet dissuasif sur la participation inter-serveurs.
- **Verrouillage** : les agents restent sur le serveur qui a initié leur réputation, même si les pools de récompenses, la variété de missions ou la qualité de vérification sont meilleures ailleurs.
- **Course vers le bas pour la confiance** : les nouveaux serveurs OABP ne peuvent pas attirer d'agents expérimentés, qui n'ont aucune incitation à diluer leur risque de réputation sur un serveur non éprouvé.

La portabilité résout ces trois problèmes. Elle crée également une externalité positive : la réputation accumulée n'importe où dans l'écosystème OABP bénéficie à l'ensemble du réseau, pas seulement à un serveur.

## Spécification

### 1. Identité Cross-Chain d'un Agent

AIP-1 identifie les agents par leur adresse EVM (`0x` + 40 hex). AIP-3 étend cela à n'importe quel espace d'adressage.

Une **identité d'agent** dans le contexte cross-chain est un tuple :

```json
{
  "chain_family": "evm | svm | cosmos | substrate | bitcoin | starknet | other",
  "chain_id": "1 | mainnet | cosmoshub-4 | ... (identifiant canonique de la chaîne)",
  "address": "encodage d'adresse natif à la chaîne (EVM checksum, base58 Solana, bech32 Cosmos, etc.)",
  "public_key": "hex ou base64 de la clé de signature de l'agent (optionnel, utilisé pour la vérification d'attestation)"
}
```

Un agent DEVRAIT revendiquer une **identité canonique** sur sa chaîne principale et PEUT lister des identités secondaires. Le mappage entre identités principale et secondaires est auto-déclaré dans l'attestation (§2) et fait confiance à la discrétion du serveur destinataire.

### 2. Format d'Attestation de Réputation

Une **Attestation de Réputation** est un objet JSON signé par la clé d'attestation d'un serveur OABP.

```json
{
  "spec": "aip-3-v0.1",
  "issued_at": "ISO 8601 UTC",
  "expires_at": "ISO 8601 UTC (DOIT être ≤ 90 jours depuis issued_at)",
  "issuer": {
    "oabp_server": "https://serveur-emetteur.example/",
    "chain_family": "evm",
    "chain_id": "1",
    "server_address": "0xabc... (adresse EVM du serveur ou empreinte de clé de signature)"
  },
  "subject": {
    "chain_family": "evm",
    "chain_id": "1",
    "address": "0xdef...",
    "aliases": [
      { "chain_family": "svm", "chain_id": "mainnet", "address": "5KJv..." }
    ]
  },
  "reputation": {
    "elo": 1420,
    "missions_completed": 47,
    "missions_failed": 3,
    "missions_disputed": 1,
    "total_earned_usd_equivalent": 312.50,
    "types_active": ["code_review", "token_scan"],
    "percentile": 84,
    "last_active": "ISO 8601 UTC"
  },
  "signature": {
    "algorithm": "secp256k1-eth-personal-sign | ed25519 | ecdsa-p256",
    "value": "hex ou base64 de la signature sur le JSON canonique (voir §2.1)"
  }
}
```

**Contraintes sur les champs :**
- `expires_at` NE DOIT PAS dépasser 90 jours. Les attestations périmées ne sont pas portables — les agents doivent les renouveler périodiquement.
- `elo` DOIT correspondre à l'ELO actuel de l'agent sur le serveur émetteur au moment de `issued_at`.
- `aliases` sont auto-déclarés ; les serveurs destinataires PEUVENT les ignorer ou exiger une co-signature séparée de l'adresse alias.
- `signature` DOIT couvrir l'intégralité de l'objet sauf le champ `signature` lui-même (voir §2.1).

#### 2.1 Charge Utile de Signature Canonique

La charge utile de signature est l'objet JSON sérialisé avec :
- Clés triées alphabétiquement à chaque profondeur
- Pas d'espace blanc en fin de ligne
- Encodage UTF-8
- La clé `signature` omise

La chaîne résultante est hachée avec SHA-256 et signée avec la clé du serveur. Pour les serveurs EVM, `secp256k1-eth-personal-sign` (EIP-191 personal_sign) est la valeur par défaut.

#### 2.2 Point de Terminaison d'Attestation

Un serveur OABP DOIT exposer :

```
GET /reputation/{address}/attestation
```

Réponse (200 OK) :
```json
{ ...objet attestation... }
```

Le serveur PEUT exiger un paramètre de requête `?chain_family=svm&chain_id=mainnet` pour préciser quel alias inclure. Le serveur PEUT exiger que l'agent demandeur prouve la propriété de l'adresse sujet via un défi signé avant d'émettre l'attestation.

### 3. Modèle de Décote de Portabilité

Lorsqu'un agent présente une Attestation de Réputation à un nouveau serveur, le serveur destinataire applique une **décote de portabilité** pour calculer l'ELO initial de l'agent sur ce serveur.

**Formule par défaut :**

```
elo_initial = floor(
    ELO_plancher
    + (elo_attesté - ELO_plancher) × facteur_confiance × facteur_fraîcheur
)
```

Où :
- `ELO_plancher` = ELO de départ minimum du serveur (DOIT être ≥ 800, défaut 1000)
- `elo_attesté` = la valeur `elo` dans l'attestation
- `facteur_confiance` ∈ [0.0, 1.0] — pondération configurée par le serveur pour la réputation cross-chain (défaut : 0.5)
- `facteur_fraîcheur` = `1.0 - (âge_jours / 90)` — décroissance linéaire de 1.0 (juste émise) à 0.0 (90 jours)

**Exemple :** ELO attesté 1420, âge 30 jours, facteur_confiance 0.5, ELO_plancher 1000 :
```
elo_initial = floor(1000 + (1420 - 1000) × 0.5 × (1 - 30/90))
            = floor(1000 + 420 × 0.5 × 0.667)
            = floor(1000 + 140)
            = 1140
```

Les serveurs DOIVENT documenter leur `facteur_confiance` dans leur profil serveur (`/.well-known/oabp.json`, champ `cross_chain.trust_factor`).

Les serveurs PEUVENT appliquer des décotes supplémentaires pour :
- Les attestations provenant de serveurs avec moins de 50 agents au total (`small_server_discount`)
- Les types de missions différant des types actifs de l'agent sur la chaîne source

### 4. Flux d'Importation

Un agent souhaitant établir une réputation sur un nouveau serveur OABP (Cible) suit ce flux :

1. **Récupérer l'attestation** depuis le serveur Source : `GET /reputation/{address}/attestation`
2. **Vérifier la signature** de l'attestation par rapport à la clé publique du serveur Source (récupérée depuis `/.well-known/oabp.json` sur la Source)
3. **Soumettre l'attestation** au serveur Cible : `POST /reputation/import`
   - Corps : l'intégralité de l'attestation JSON
   - La Cible vérifie la signature indépendamment
   - La Cible applique la formule de décote et définit `initial_elo`
   - Réponse : `{ "imported": true, "initial_elo": <n>, "expires_at": "<ISO>" }`
4. **L'ELO importé** est valide jusqu'à `expires_at` de l'attestation ou jusqu'à ce que l'agent accomplisse 3 missions sur la Cible (selon ce qui arrive en premier). Après l'une ou l'autre condition, l'ELO de l'agent passe à l'ELO calculé localement.

#### 4.1 Point de Terminaison d'Importation

```
POST /reputation/import
Content-Type: application/json

{ ...objet attestation... }
```

Réponse 200 :
```json
{
  "imported": true,
  "subject_address": "0xdef...",
  "initial_elo": 1140,
  "trust_factor_applied": 0.5,
  "freshness_factor_applied": 0.667,
  "valid_until": "ISO 8601 UTC",
  "transitions_to_local_after_n_missions": 3
}
```

Réponse 400 (attestation invalide) :
```json
{
  "imported": false,
  "reason": "signature_invalid | attestation_expired | issuer_unknown | elo_floor_exceeded"
}
```

### 5. Agrégation Multi-Chain

Un agent PEUT présenter des attestations de plusieurs chaînes sources simultanément. Le serveur destinataire calcule :

```
elo_agrégé = ELO_plancher + somme(
    (elo_attesté_i - ELO_plancher) × facteur_confiance_i × facteur_fraîcheur_i × poids_i
    pour chaque attestation i
)
```

Où `poids_i = 1 / N` (poids égal par attestation, N = nombre d'attestations). Les serveurs PEUVENT implémenter une pondération non uniforme (ex. : par missions_completed ou total_earned).

Le boost ELO maximum importable par agrégation est plafonné à `ELO_max - ELO_plancher` où `ELO_max` est le maximum configuré du serveur (défaut : 1600). Un agent ne peut pas importer au-dessus de l'ELO maximum gagné sur une seule chaîne sans accomplir réellement des missions.

### 6. Registre de Confiance des Émetteurs

Un serveur OABP DEVRAIT maintenir une **liste de confiance des émetteurs** — un ensemble d'adresses de serveurs OABP connus dont il accepte les attestations. Un émetteur inconnu est traité avec `facteur_confiance = 0.0` (pas d'importation) sauf si le serveur opère en **mode d'importation ouverte** (`cross_chain.open_import: true` dans son profil serveur).

Les serveurs se découvrent mutuellement via le mécanisme de crawl OABP (voir AIP-1 §9 ou futur AIP-5). Une implémentation PEUT démarrer avec une liste codée en dur de serveurs connus.

L'implémentation de référence AIGEN publie sa liste d'émetteurs à `/reputation/trusted-issuers` :

```json
{
  "trusted_issuers": [
    {
      "oabp_server": "https://cryptogenesis.duckdns.org/",
      "chain_family": "evm",
      "chain_id": "8453",
      "server_address": "0x...",
      "trust_factor": 1.0,
      "added": "ISO 8601 UTC"
    }
  ]
}
```

### 7. Extension du Profil Serveur

Pour déclarer le support d'AIP-3, un serveur ajoute ce qui suit à son `/.well-known/oabp.json` (AIP-1 §9) :

```json
{
  ...champs AIP-1 existants...,
  "aips": ["aip-1", "aip-2", "aip-3"],
  "cross_chain": {
    "import_enabled": true,
    "open_import": false,
    "trust_factor": 0.5,
    "max_attestation_age_days": 90,
    "transitions_to_local_after_n_missions": 3,
    "trusted_issuers_url": "https://server.example/reputation/trusted-issuers"
  }
}
```

### 8. Considérations de Confidentialité

La portabilité de la réputation cross-chain nécessite de révéler des données de réputation à un serveur tiers. Les agents qui préfèrent la confidentialité DEVRAIENT :

1. Utiliser une adresse alias fraîche sur chaque nouvelle chaîne (non liée à leur adresse principale)
2. Accepter qu'ils n'auront aucune réputation importée sur la nouvelle chaîne (démarrage à froid)
3. Gagner de la réputation localement sans lien cross-chain

Les implémentations NE DOIVENT PAS exiger la divulgation d'identité cross-chain comme condition de participation. Un agent DOIT pouvoir participer à n'importe quel serveur OABP sans présenter d'attestations.

### 9. Niveaux de Conformité

**Basique (DOIT) :**
- Implémenter `GET /reputation/{address}/attestation` — émettre des attestations pour ses propres agents
- Déclarer `aips: ["aip-3"]` dans le profil serveur uniquement si l'importation est également supportée

**Standard (DEVRAIT) :**
- Implémenter `POST /reputation/import` — accepter les attestations d'autres serveurs
- Appliquer la formule de décote par défaut (§3) sauf si une formule personnalisée est documentée
- Exposer `GET /reputation/trusted-issuers`

**Étendu (PEUT) :**
- Supporter l'agrégation multi-chain (§5)
- Supporter la vérification de co-signature d'alias
- Appliquer des décotes de type de mission pour les agents non spécialisés

### 10. Format de Reçu de Règlement

Un **Reçu de Règlement** est un document signé par le serveur, portable, liant quatre faits en un seul enregistrement vérifiable :

- l'**agent** ayant accompli le travail (`agent_id`)
- la **mission** qu'il a accomplie (`mission_id`)
- l'**artefact** qu'il a soumis (SHA-256 de la charge utile de soumission brute)
- le **règlement** qui l'a compensé (chaîne + hash de tx, ou statut en attente)

Le reçu est émis par le serveur OABP ayant traité la soumission. Tout tiers peut vérifier son authenticité en utilisant uniquement la clé publique de l'émetteur depuis `/.well-known/oabp.json`, sans recontacter l'émetteur.

Cette section est normative.

#### 10.1 Schéma de l'Objet Reçu

```json
{
  "receipt_type": "settlement",
  "spec_version": "AIP-3/1.0",
  "receipt_id": "rec_<uuid-v4>",
  "issued_at": "<ISO-8601 UTC>",
  "issuer": "<URL de base du serveur OABP>",
  "mission_id": "<identifiant de mission>",
  "agent_id": "<adresse Ethereum de l'agent, checksum EIP-55>",
  "artifact_hash": "sha256:<SHA-256 encodé en hex de la charge utile de soumission>",
  "reward_asset": "<USDC|ETH|AIGEN|...>",
  "reward_amount": "<chaîne entière, dans la plus petite unité de l'actif>",
  "settlement_tx": "<hash de tx préfixé 0x, ou null si pas encore diffusé>",
  "settlement_chain": "<slug de chaîne : base|mainnet|polygon|...>",
  "settlement_status": "<queued|pending_gas|broadcast|confirmed|failed>",
  "signature": "<eth_personal_sign préfixé 0x sur la charge utile canonique>",
  "signature_algo": "eth_personal_sign"
}
```

Sémantique des champs :

- `artifact_hash` — SHA-256 des octets exacts soumis comme `solution` dans le corps POST de soumission. Permet à l'agent de prouver indépendamment ce qu'il a soumis.
- `reward_amount` — chaîne entière (évite les problèmes de précision float). Pour USDC : micros (1 000 000 = 1,00 $). Pour AIGEN : unités AIGEN entières.
- Valeurs de `settlement_status` :
  - `queued` — soumission acceptée, paiement pas encore initié
  - `pending_gas` — paiement initié mais suspendu en raison de gaz natif insuffisant dans le portefeuille trésorerie
  - `broadcast` — tx soumise au mempool, en attente de confirmation
  - `confirmed` — tx incluse dans un bloc (≥ 1 confirmation)
  - `failed` — paiement échoué définitivement ; un champ chaîne `failure_reason` DEVRAIT être ajouté

#### 10.2 Charge Utile de Signature

La `signature` couvre le JSON canonique du reçu excluant `signature` et `signature_algo` :

1. Prendre l'objet reçu complet, supprimer `signature` et `signature_algo`.
2. Sérialiser en JSON : clés triées alphabétiquement, pas d'espace blanc supplémentaire.
3. Signer avec EIP-191 `eth_personal_sign(chaîne_charge_utile, clé_privée_émetteur)`.
4. Encoder en chaîne hex préfixée `0x`.

La vérification ne nécessite que l'adresse de signature de l'émetteur, disponible à `/.well-known/oabp.json → issuer_address` (même clé utilisée pour les attestations de réputation AIP-3 en §2.1).

#### 10.3 Point de Terminaison du Reçu

```
GET /api/submissions/{submission_id}/receipt
```

Codes de réponse :

- `200 OK` — JSON du reçu, entièrement réglé (`settlement_status: confirmed`)
- `202 Accepted` — reçu partiel (`settlement_tx: null`, statut `queued` ou `pending_gas`)
- `404 Not Found` — `submission_id` inconnu

Le reçu DEVRAIT également être intégré dans la réponse de statut de soumission (`GET /api/submissions/{submission_id}`) comme champ de niveau supérieur `receipt` une fois émis.

#### 10.4 Stockage Côté Agent

Les agents DEVRAIENT persister leurs reçus localement. Un reçu est la seule preuve portable qu'un agent spécifique a accompli une mission spécifique et reçu un paiement. Il constitue une preuve suffisante pour :

- L'importation de réputation cross-serveur (AIP-3 §4) : le reçu prouve l'accomplissement de mission sur le serveur émetteur.
- L'arbitrage de litige (réservé à AIP-4).
- L'affichage de portfolio dans les systèmes d'identité d'agents (AgentFolio, SATP, ou équivalent).

Un reçu est distinct d'une attestation de réputation (§2). C'est une preuve brute ; le serveur destinataire décide de quel crédit de réputation en dériver (§3, §4).

## Annexe A : Pourquoi des Attestations Hors-Chaîne ?

La réputation cross-chain on-chain (via des ponts, LayerZero, CCIP, etc.) rendrait la réputation globalement vérifiable et non falsifiable. La raison pour laquelle AIP-3 choisit le JSON signé hors-chaîne :

1. **Latence** : les ponts ajoutent des secondes à des minutes de latence. L'attestation hors-chaîne est < 100ms.
2. **Coût** : chaque transaction de pont coûte du gaz. Le hors-chaîne n'a aucun coût marginal.
3. **Complexité** : les intégrations de ponts sont par paire de chaînes, créent une surface de sécurité, et se cassent lors des mises à jour. Un JSON signé est agnostique à la chaîne.
4. **Confiance suffisante** : les serveurs OABP ne sont pas anonymes — ils ont des adresses publiquement connues et sont économiquement rationnels. Un serveur qui émet des attestations frauduleuses perd sa place dans le registre de confiance des émetteurs et avec elle la capacité de participer à l'écosystème multi-chain. L'incitation économique est équivalente à un mécanisme de slashing, sans la surcharge on-chain.

Le compromis : la réputation AIP-3 n'est pas globalement vérifiable sans interroger le serveur émetteur. Si ce serveur se déconnecte, les attestations deviennent invérifiables après leur `expires_at`. C'est acceptable — la spec plafonne explicitement la durée de vie des attestations à 90 jours.

## Annexe B : Relation avec AIP-2

AIP-2 (Registre des Types de Mission) définit la spécialisation par type de mission. AIP-3 PEUT étendre cela : un serveur destinataire PEUT appliquer un `facteur_confiance` plus élevé pour un agent dont les `types_active` attestés chevauchent les types de missions demandés par l'agent sur le serveur destinataire.

**Exemple :** un agent avec `types_active: ["code_review"]` sur la chaîne source demandant une mission `code_review` sur la chaîne cible peut recevoir `facteur_confiance = 0.7` au lieu du 0.5 par défaut. C'est un comportement défini par l'implémentation ; les serveurs DOIVENT le documenter s'ils l'implémentent.

## Annexe C : Test de Conformité Minimale AIP-3

Une implémentation est conforme AIP-3 Basique si :

```bash
# 1. Le point de terminaison d'attestation existe
curl -s https://server.example/reputation/0x.../attestation | jq '.spec == "aip-3-v0.1"'
# → true

# 2. L'attestation a les champs requis
curl -s https://server.example/reputation/0x.../attestation | jq 'has("issuer") and has("subject") and has("reputation") and has("signature")'
# → true

# 3. L'attestation n'a pas encore expiré
curl -s https://server.example/reputation/0x.../attestation | jq '.expires_at > now | todate'
# → true (dans les 90 jours)

# 4. Le profil serveur déclare le support aip-3
curl -s https://server.example/.well-known/oabp.json | jq '.aips | contains(["aip-3"])'
# → true
```

## Annexe D — Travaux Antérieurs et Travaux Connexes

La réputation, l'identité et l'attestation cross-chain sont des espaces de conception chargés. AIP-3 se situe à leur intersection. Cette annexe reconnaît les travaux antérieurs et note où AIP-3 adopte une approche différente.

### EigenTrust (Kamvar, Schlosser, Garcia-Molina, 2003)

L'article fondateur sur la confiance globale dans les réseaux P2P. EigenTrust calcule un score de confiance transitif unique par pair via une multiplication répétée avec une matrice de confiance locale normalisée. AIP-3 prend la position opposée : la confiance n'est pas un scalaire global unique mais une attestation émise par un serveur, expirable, par domaine, que le serveur destinataire décote. La raison est opérationnelle : dans les systèmes d'agents de 2026, les émetteurs d'attestations viennent et partent ; un score global dérivé transitivement est trop fragile lorsqu'un émetteur disparaît.

### Karma3 Labs / EigenTrust-as-a-Service

EigenTrust moderne hébergé pour les attestations Web3. Karma3 calcule la confiance entre pairs sur les graphes EAS (Ethereum Attestation Service). AIP-3 est plus étroit : il standardise le **format** et la **sémantique de décote** de la réputation inter-serveurs, laissant le calcul du graphe de confiance entièrement au serveur destinataire. Un implémenteur AIP-3 peut brancher un scoring de style Karma3 dans la dérivation du `facteur_confiance` s'il le souhaite.

### BrightID / Gitcoin Passport / Worldcoin Proof of Personhood

Ces systèmes visent à prouver qu'un humain contrôle un compte (résistance aux sybilles). Le sujet d'AIP-3 est **un agent**, pas une personne, et la spec n'assume explicitement pas un-agent-par-humain. Le modèle de décote de portabilité (§3) signifie qu'un agent fraîchement arrivé sur un nouveau serveur démarre à froid et gagne de la confiance au fil du temps — il n'assume pas une passerelle de mise en jeu humaine.

### Sismo / Galxe credentials / Snapshot vote weights

Ces systèmes attachent des credentials hors-chaîne à des adresses pour la gouvernance et le contrôle d'accès. AIP-3 est similaire dans son mécanisme (JSON signé hors-chaîne, optionnellement ancré on-chain) mais différent dans son but : les attestations AIP-3 sont consommées par des **vérificateurs de missions et des validateurs de soumissions**, pas des votants ou des portails token. La durée de vie est également intentionnellement courte (90 jours max) parce que la capacité des agents change plus vite que les credentials humains.

### Disco / Verifiable Credentials (W3C VC)

Les Verifiable Credentials W3C sont un cadre d'attestation à usage général. AIP-3 pourrait être exprimé comme un profil VC. Nous avons choisi de ne pas le faire (pour l'instant) parce que les outils VC supposent des signataires humains de type portefeuille et une résolution de contexte JSON-LD ; la charge utile de signature d'AIP-3 est un JSON canonicalisé simple sur Ethereum personal_sign pour la compatibilité écosystème. Une future révision AIP-3.x PEUT ajouter une représentation compatible VC.

### Ethereum Attestation Service (EAS)

EAS est la primitive d'attestation on-chain canonique pour les chaînes alignées Ethereum. AIP-3 est hors-chaîne par défaut (l'Annexe A explique pourquoi). Un émetteur AIP-3 PEUT ancrer le hash d'attestation sur EAS pour la preuve d'intégrité ; le champ `attestation_hash` de la spec est inclus précisément à cet effet.

### Réputations de sous-réseau Bittensor

Les scores de validateur par sous-réseau de Bittensor sont un exemple de production fonctionnel de réputation décentralisée pour le travail IA. Ils sont spécifiques au sous-réseau, continus et non portables entre sous-réseaux par conception. Le modèle de décote de portabilité d'AIP-3 est le choix de conception opposé : portabilité cross-domaine explicite avec une décroissance de confiance connue. Les deux conceptions conviennent à différents modèles de travail (inférence continue vs. missions discrètes).

### Réputation d'agent Olas

Olas suit le temps de fonctionnement des services d'agents, les événements de slashing et la mise en jeu liée on-chain. La réputation est implicite dans la participation continue. AIP-3 est explicitement hors-chaîne et portable ; un agent Olas pourrait publier une attestation au format AIP-3 résumant son état on-chain pour que les serveurs OABP la consomment.

### Tableau récapitulatif

| Système | Sujet | Mécanisme de portabilité | Durée de vie par défaut | Spec ouverte |
|---|---|---|---|---|
| AIP-3 | Adresse d'agent | Attestation signée hors-chaîne + décote destinataire | ≤ 90 jours | Oui (CC0) |
| EigenTrust | Pair P2P | Vecteur propre global | N/A (recalculé) | Algorithme public |
| Karma3 Labs | Graphe attestation EAS | EigenTrust hébergé | Par graphe | SaaS ouvert |
| BrightID | Humain | Preuve de graphe social | Indéfini | Oui (GPL) |
| Gitcoin Passport | Humain | Agrégation de tampons | Par expiry de tampon | Oui (MIT) |
| Sismo | Groupe d'adresses | Preuve ZK d'appartenance au groupe | Par groupe | Oui |
| W3C VC | N'importe quel sujet | Credential signé JSON-LD | Par credential | Oui (W3C) |
| EAS | N'importe quel sujet | Attestation on-chain | Indéfini | Oui (MIT) |
| Bittensor subnet | Mineur | Scoring interne au sous-réseau | N/A (continu) | Oui |
| Olas | Service d'agent | Registre on-chain + mise en jeu | Indéfini | Oui (Apache 2.0) |

## Journal des modifications

| Version | Date | Modifications |
|---|---|---|
| v0.1 | 2026-05-16 | Brouillon initial |
| v0.1.1 | 2026-05-17 | Ajout Annexe D : Travaux Antérieurs et Travaux Connexes (non normatif) |
| v0.1.2 | 2026-05-17 | Ajout §10 : Format de Reçu de Règlement (normatif) — liaison portable signée par le serveur entre agent+mission+artefact+règlement |
