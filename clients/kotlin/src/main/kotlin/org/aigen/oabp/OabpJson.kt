package org.aigen.oabp

import kotlinx.serialization.json.Json

/**
 * Centralized kotlinx.serialization [Json] configuration for the OABP wire contract.
 *
 * Keeps the encode/decode behaviour consistent everywhere the SDK touches JSON:
 *
 *  - `ignoreUnknownKeys = true` — forward compatibility with fields the server adds later;
 *  - `explicitNulls = false` — omit `null` fields from request bodies (matches the API's
 *    optional-field convention);
 *  - `isLenient = true` — tolerate minor wire quirks (e.g. unquoted/stringified numbers);
 *  - `encodeDefaults = false` — don't serialize defaulted optional fields unnecessarily.
 *
 * The instance is immutable and safe to share. The same configuration is installed into the
 * Ktor client's content negotiation in [OabpClient].
 */
public val OabpJson: Json =
    Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        isLenient = true
        encodeDefaults = false
    }
