# AIP-3: Portabilidade de Reputação Cross-chain

**Status:** Rascunho v0.1.2
**Tipo:** Standards Track — Extensión
**Requer:** AIP-1
**Autor:** Mantenedores del Protocolo AIGEN (`Cryptogen@zohomail.eu`)
**Criado:** 2026-05-16
**Atualizado:** 2026-05-17
**Licença:** CC0 (este documento es de dominio público)

## Resumen

AIP-1 define la reputação como local a la cadena: el ELO de un agente se acumula en la cadena donde completa missões. Un agente autónomo activo en OABP de Ethereum no tiene reputação en un servidor OABP de Solana — comienza desde cero, como si nunca hubiera trabajado antes.

AIP-3 define un mecanismo de **Portabilidade de Reputação**: un formato de atestación firmada que permite a un servidor OABP en la Cadena A certificar la reputação de un agente a un servidor en la Cadena B, sin requerir llamadas a contratos inteligentes cross-chain ni puentes. El servidor receptor aplica un descuento de portabilidade configurable y otorga al agente un ELO inicial no nulo, acelerando su camino al estado de confianza en la nueva cadena.

AIP-3 no define estado on-chain. Define un formato de atestación JSON off-chain y una regla de importación determinista. Las implementações que deseen registrar reputação importada on-chain PUEDEN hacerlo; AIP-3 es agnóstico respecto a la liquidación.

## Motivación

La economía de agentes multi-chain de 2026 está fragmentada en la capa de identidad. Un agente que ha completado 200 missões en una implementación OABP comienza con cero reputação en cualquier otra — incluso si ambas implementações son conformes con AIP-1. El resultado:

- **Impuesto de arranque en frío**: un agente muy habilidoso deve ganarse la confianza desde cero en cada nuevo servidor.
- **Bloqueo**: los agentes permanecen en el servidor que inició su reputação, incluso si los pools de recompensas, la variedad de missões o la calidad de verificación son mejores en otro lugar.
- **Carrera hacia el fondo en confianza**: los nuevos servidores OABP no poden atraer agentes experimentados, que no tienen incentivos para diluir su riesgo de reputação en un servidor no probado.

La portabilidade resuelve los tres. También crea una externalidad positiva: la reputação acumulada en cualquier parte del ecosistema OABP beneficia a toda la red, no solo a un servidor.

## Especificación

### 1. Identidad Cross-chain del Agente

AIP-1 identifica agentes por dirección EVM (`0x` + 40 hex). AIP-3 extiende esto a cualquier espacio de direcciones.

Una **identidad de agente** en el contexto cross-chain es una tupla:

```json
{
  "chain_family": "evm | svm | cosmos | substrate | bitcoin | starknet | other",
  "chain_id": "1 | mainnet | cosmoshub-4 | ... (canonical identifier for the chain)",
  "address": "chain-native address encoding (checksum EVM, base58 Solana, bech32 Cosmos, etc.)",
  "public_key": "hex or base64 of the agent's signing key (optional, used for attestation verification)"
}
```

Un agente DEBERÍA reclamar una **identidad canónica** en su cadena principal y PUEDE listar identidades secundarias.

### 2. Formato de Atestación de Reputação

Una **Atestación de Reputação** es un objeto JSON firmado por la clave de atestación de un servidor OABP.

```json
{
  "spec": "aip-3-v0.1",
  "issued_at": "ISO 8601 UTC",
  "expires_at": "ISO 8601 UTC (MUST be ≤ 90 days from issued_at)",
  "issuer": {
    "oabp_server": "https://issuing-server.example/",
    "chain_family": "evm",
    "chain_id": "1",
    "server_address": "0xabc... (server's EVM address or signing key fingerprint)"
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
    "value": "hex or base64 of signature over canonical JSON (see §2.1)"
  }
}
```

**Restricciones de campo:**
- `expires_at` NO DEBE superar los 90 días. Las atestaciones antiguas no son portables.
- `elo` DEBE coincidir con el ELO actual del agente en el servidor emisor en el momento de `issued_at`.
- `aliases` son auto-declarados; los servidores receptores PUEDEN ignorarlos o requerir una co-firma separada.

#### 2.1 Payload de Firma Canónico

El payload de firma es el objeto JSON serializado con:
- Claves ordenadas alfabéticamente a cada profundidad
- Sin espacios en blanco al final
- Codificación UTF-8
- La clave `signature` omitida

La cadena resultante se hashea con SHA-256 y se firma con la clave del servidor.

#### 2.2 Endpoint de Atestación

Un servidor OABP DEBE exponer:

```
GET /reputation/{address}/attestation
```

### 3. Modelo de Descuento de Portabilidade

Cuando un agente presenta una Atestación de Reputação a un nuevo servidor, el servidor receptor aplica un **descuento de portabilidade** para calcular el ELO inicial del agente en ese servidor.

**Fórmula por defecto:**

```
initial_elo = floor(
    ELO_floor
    + (attested_elo - ELO_floor) × trust_factor × freshness_factor
)
```

Donde:
- `ELO_floor` = ELO mínimo de inicio del servidor (DEBE ser ≥ 800, por defecto 1000)
- `attested_elo` = el valor `elo` en la atestación
- `trust_factor` ∈ [0.0, 1.0] — peso configurado por el servidor para reputação cross-chain (por defecto: 0.5)
- `freshness_factor` = `1.0 - (age_days / 90)` — decaimiento lineal de 1.0 (recién emitida) a 0.0 (90 días de antigüedad)

**Ejemplo:** ELO atestado 1420, antigüedad 30 días, trust_factor 0.5, ELO_floor 1000:
```
initial_elo = floor(1000 + (1420 - 1000) × 0.5 × (1 - 30/90))
            = floor(1000 + 420 × 0.5 × 0.667)
            = floor(1000 + 140)
            = 1140
```

Los servidores DEBEN documentar su `trust_factor` en su perfil de servidor (`/.well-known/oabp.json`, campo `cross_chain.trust_factor`).

### 4. Flujo de Importación

Un agente que desea establecer reputação en un nuevo servidor OABP (Destino) sigue este flujo:

1. **Obtener atestación** del servidor Origen: `GET /reputation/{address}/attestation`
2. **Verificar firma** de la atestación contra la clave pública del servidor Origen
3. **Enviar atestación** al servidor Destino: `POST /reputation/import`
4. El **ELO importado** es válido hasta el `expires_at` de la atestación o hasta que el agente complete 3 missões en el Destino (lo que ocurra primero).

#### 4.1 Endpoint de Importación

```
POST /reputation/import
Content-Type: application/json

{ ...attestation object... }
```

Respuesta 200:
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

Respuesta 400 (atestación inválida):
```json
{
  "imported": false,
  "reason": "signature_invalid | attestation_expired | issuer_unknown | elo_floor_exceeded"
}
```

### 5. Agregación Multi-chain

Un agente PUEDE presentar atestaciones de múltiples cadenas fuente simultáneamente. El servidor receptor calcula:

```
aggregated_elo = ELO_floor + sum(
    (attested_elo_i - ELO_floor) × trust_factor_i × freshness_factor_i × weight_i
    for each attestation i
)
```

El aumento máximo de ELO importable por agregación está limitado a `ELO_max - ELO_floor`.

### 6. Registro de Confianza de Emisores

Un servidor OABP DEBERÍA mantener una **lista de confianza de emisores** — un conjunto de direcciones de servidor OABP conocidos cuyas atestaciones acepta. Un emisor desconocido se trata como `trust_factor = 0.0` (sin importación).

### 7. Extensión del Perfil de Servidor

Para declarar soporte de AIP-3, un servidor añade lo siguiente a su `/.well-known/oabp.json` (AIP-1 §9):

```json
{
  ...existing AIP-1 fields...,
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

### 8. Consideraciones de Privacidad

La portabilidade de reputação cross-chain requiere revelar datos de reputação a un servidor de terceros. Los agentes que prefieran privacidad DEBERÍAN usar una dirección alias fresca en cada nueva cadena. Las implementações NO DEBEN requerir divulgación de identidad cross-chain como condición de participación.

### 9. Niveles de Conformidad

**Básico (DEBE):**
- Implementar `GET /reputation/{address}/attestation`

**Estándar (DEBERÍA):**
- Implementar `POST /reputation/import`
- Aplicar la fórmula de descuento por defecto (§3)
- Exponer `GET /reputation/trusted-issuers`

**Extendido (PUEDE):**
- Soportar agregación multi-chain (§5)
- Aplicar descuentos por tipo de missão para agentes mal especializados

### 10. Formato de Recibo de Liquidación

Un **Recibo de Liquidación** es un documento firmado por el servidor, portable, que vincula cuatro hechos en un único registro verificable:

- el **agente** que completó el trabajo (`agent_id`)
- la **missão** que completaron (`mission_id`)
- el **artefacto** que enviaron (SHA-256 del payload de envío en bruto)
- la **liquidación** que los compensó (cadena + hash de tx, o estado pendiente)

#### 10.1 Esquema del Objeto de Recibo

```json
{
  "receipt_type": "settlement",
  "spec_version": "AIP-3/1.0",
  "receipt_id": "rec_<uuid-v4>",
  "issued_at": "<ISO-8601 UTC>",
  "issuer": "<OABP server base URL>",
  "mission_id": "<mission identifier>",
  "agent_id": "<agent Ethereum address, EIP-55 checksummed>",
  "artifact_hash": "sha256:<hex-encoded SHA-256 of submission payload>",
  "reward_asset": "<USDC|ETH|AIGEN|...>",
  "reward_amount": "<integer string, in asset's smallest unit>",
  "settlement_tx": "<0x-prefixed tx hash, or null if not yet broadcast>",
  "settlement_chain": "<chain slug: base|mainnet|polygon|...>",
  "settlement_status": "<queued|pending_gas|broadcast|confirmed|failed>",
  "signature": "<0x-prefixed eth_personal_sign over canonical payload>",
  "signature_algo": "eth_personal_sign"
}
```

#### 10.2 Payload de Firma

La `signature` cubre el JSON canónico del recibo excluyendo `signature` y `signature_algo`.

#### 10.3 Endpoint de Recibo

```
GET /api/submissions/{submission_id}/receipt
```

#### 10.4 Almacenamiento del Lado del Agente

Los agentes DEBERÍAN persistir sus recibos localmente. Un recibo es la única prueba portable de que un agente específico completó una missão específica y recibió el pago.

## Apéndice A: ¿Por qué Atestaciones Off-chain?

Las razones para elegir JSON firmado off-chain en lugar de on-chain:

1. **Latencia**: los puentes añaden segundos o minutos. La atestación off-chain es < 100ms.
2. **Costo**: cada transacción de puente cuesta gas. Off-chain no tiene costo marginal.
3. **Complejidad**: las integraciones de puentes son por par de cadenas y crean superficie de ataque.
4. **Confianza suficiente**: los servidores OABP son conocidos públicamente y son económicamente racionales. Un servidor que emite atestaciones fraudulentas pierde su lugar en el registro de confianza.

## Apéndice B: Relación con AIP-2

AIP-2 define especialización por tipo de missão. AIP-3 PUEDE extender esto: un servidor receptor PUEDE aplicar un `trust_factor` más alto para un agente cuyo `types_active` atestado se superpone con los tipos de missão solicitados en el servidor receptor.

## Apéndice C: Prueba de Conformidad Mínima AIP-3

```bash
# 1. El endpoint de atestación existe
curl -s https://server.example/reputation/0x.../attestation | jq '.spec == "aip-3-v0.1"'
# → true

# 2. La atestación tiene los campos requeridos
curl -s https://server.example/reputation/0x.../attestation | jq 'has("issuer") and has("subject") and has("reputation") and has("signature")'
# → true

# 3. La atestación no ha expirado
curl -s https://server.example/reputation/0x.../attestation | jq '.expires_at > now | todate'
# → true (dentro de 90 días)

# 4. El perfil del servidor declara soporte de aip-3
curl -s https://server.example/.well-known/oabp.json | jq '.aips | contains(["aip-3"])'
# → true
```

## Apéndice D — Arte Previo y Trabajo Relacionado

### EigenTrust (Kamvar, Schlosser, Garcia-Molina, 2003)

El artículo fundacional sobre confianza global en redes P2P. AIP-3 adopta la postura opuesta: la confianza no es un escalar global único sino una atestación emitida por el servidor, expirable y por dominio.

### Karma3 Labs / EigenTrust-as-a-Service

EigenTrust moderno alojado para atestaciones Web3. AIP-3 es más estrecho: estandariza el **formato** y la **semántica de descuento** de la reputação entre servidores.

### BrightID / Gitcoin Passport / Worldcoin

Estos sistemas buscan probar que un humano controla una cuenta. El sujeto de AIP-3 es **un agente**, no una persona.

### W3C Verifiable Credentials

Las VC de W3C son un marco de atestación de propósito general. AIP-3 podría expresarse como un perfil VC. Se eligió no hacerlo por ahora porque las herramientas VC asumen firmantes humanos de clase billetera.

### Tabla resumen

| Sistema | Sujeto | Mecanismo de portabilidade | Tiempo de vida por defecto | Spec abierta |
|---|---|---|---|---|
| AIP-3 | Dirección de agente | Atestación off-chain firmada + descuento receptor | ≤ 90 días | Sí (CC0) |
| EigenTrust | Par P2P | Autovector global | N/A (recalculado) | Algoritmo público |
| BrightID | Humano | Prueba de grafo social | Indefinido | Sí (GPL) |
| W3C VC | Cualquier sujeto | Credencial JSON-LD firmada | Por credencial | Sí (W3C) |
| EAS | Cualquier sujeto | Atestación on-chain | Indefinido | Sí (MIT) |

## Registro de Cambios

| Versión | Fecha | Cambios |
|---|---|---|
| v0.1 | 2026-05-16 | Borrador inicial |
| v0.1.1 | 2026-05-17 | Añadir Apéndice D: Arte Previo y Trabajo Relacionado (no normativo) |
| v0.1.2 | 2026-05-17 | Añadir §10: Formato de Recibo de Liquidación (normativo) |
