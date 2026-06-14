/**
 * Shared helpers for the Flowise OABP tool nodes:
 *   - `getBaseClasses` — mirror of Flowise's prototype-chain walker used to populate `baseClasses`;
 *   - `resolveCredential` — read the OABP base URL + bearer from a Flowise credential (or node
 *     inputs as a fallback), working both inside Flowise and standalone;
 *   - `buildClient` — turn a node's resolved inputs/credential into a concrete {@link OabpClient};
 *   - `asString` / `asNumber` — defensive readers for UI-supplied input values.
 *
 * The credential bridge is the only place that differs between "running inside Flowise" and
 * "running in a test / standalone". Inside Flowise, `getCredentialData(nodeData.credential, options)`
 * is imported from `flowise-components`; standalone there is no such module, so we lazily attempt the
 * import and fall back to reading `options.credentialData` / node inputs. Either way the nodes' code
 * is identical.
 */

import type { ICommonObject, INodeData } from "./flowise-types.js";
import { OabpSdk, type OabpClient, type OabpSdkOptions, DEFAULT_BASE_URL } from "./sdk.js";

/**
 * Reproduce Flowise's `getBaseClasses(targetClass)`: collect the names of every class in the
 * prototype chain (excluding `Object`). Flowise uses this so a Tool node can advertise
 * `[...getBaseClasses(DynamicStructuredTool)]` and be wired anywhere a `Tool`/`StructuredTool`
 * is accepted.
 */
export function getBaseClasses(targetClass: unknown): string[] {
  const result: string[] = [];
  let baseClass = targetClass as { name?: string } | undefined;
  if (typeof baseClass !== "function") return result;

  // Walk the prototype chain via Object.getPrototypeOf on the constructors.
  let current: unknown = baseClass;
  while (typeof current === "function") {
    const name = (current as { name?: string }).name;
    if (name && name !== "Object" && !result.includes(name)) {
      result.push(name);
    }
    const proto = Object.getPrototypeOf(current);
    if (!proto || proto === Function.prototype) break;
    current = proto;
  }
  return result;
}

/** The decrypted credential fields this package understands. */
export interface OabpCredentialData {
  oabpBaseUrl?: string;
  oabpApiKey?: string;
}

/**
 * Resolve the OABP credential (base URL + bearer) for a node.
 *
 * Resolution order:
 *   1. Decrypted Flowise credential via `flowise-components.getCredentialData` (production);
 *   2. `options.credentialData` if a caller injected it (tests / embedding);
 *   3. the node's own `inputs` (`baseUrl` / `apiKey`) as a last-resort override.
 */
export async function resolveCredential(
  nodeData: INodeData,
  options: ICommonObject
): Promise<OabpCredentialData> {
  let credData: ICommonObject = {};

  if (nodeData.credential) {
    // Try the real Flowise helper without a hard dependency on the module existing.
    const fromFlowise = await tryGetCredentialData(nodeData.credential, options);
    if (fromFlowise) credData = fromFlowise;
  }
  // Allow tests/embeds to pass credential data directly.
  if (!credData.oabpBaseUrl && !credData.oabpApiKey && isObject(options.credentialData)) {
    credData = options.credentialData as ICommonObject;
  }

  const inputs = (nodeData.inputs ?? {}) as ICommonObject;
  return {
    oabpBaseUrl:
      asOptionalString(credData.oabpBaseUrl) ?? asOptionalString(inputs.baseUrl),
    oabpApiKey: asOptionalString(credData.oabpApiKey) ?? asOptionalString(inputs.apiKey),
  };
}

/**
 * Build a concrete {@link OabpClient} for a node.
 *
 * If `options.oabpClient` is provided (tests/embeds inject a {@link MockOabpClient}), it is used
 * verbatim. Otherwise a live {@link OabpSdk} is constructed from the resolved credential.
 */
export async function buildClient(
  nodeData: INodeData,
  options: ICommonObject
): Promise<OabpClient> {
  const injected = options.oabpClient;
  if (injected && isOabpClient(injected)) return injected;

  const cred = await resolveCredential(nodeData, options);
  const sdkOpts: OabpSdkOptions = {
    baseUrl: cred.oabpBaseUrl || DEFAULT_BASE_URL,
  };
  if (cred.oabpApiKey) sdkOpts.apiKey = cred.oabpApiKey;
  return new OabpSdk(sdkOpts);
}

/* ------------------------------- input readers ------------------------------- */

export function asString(v: unknown, fallback = ""): string {
  if (typeof v === "string") return v;
  if (v == null) return fallback;
  return String(v);
}

export function asOptionalString(v: unknown): string | undefined {
  if (typeof v === "string" && v.length > 0) return v;
  return undefined;
}

export function asNumber(v: unknown, fallback: number): number {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

/**
 * Parse a Flowise JSON-typed input, which arrives either already-parsed (object) or as a string.
 * Returns `{}` for empty / unparseable input so callers always get an object.
 */
export function asJson(v: unknown): Record<string, unknown> {
  if (isObject(v)) return v as Record<string, unknown>;
  if (typeof v === "string" && v.trim() !== "") {
    try {
      const parsed = JSON.parse(v);
      return isObject(parsed) ? (parsed as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }
  return {};
}

/* --------------------------------- internals --------------------------------- */

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isOabpClient(v: unknown): v is OabpClient {
  return (
    isObject(v) &&
    typeof (v as { listMissions?: unknown }).listMissions === "function" &&
    typeof (v as { submit?: unknown }).submit === "function"
  );
}

/**
 * Attempt `flowise-components.getCredentialData(credentialId, options)` without making
 * `flowise-components` a compile-time dependency. Returns `undefined` if the module is absent
 * (standalone) or the lookup fails.
 */
async function tryGetCredentialData(
  credentialId: string,
  options: ICommonObject
): Promise<ICommonObject | undefined> {
  try {
    // Indirected so bundlers/tsc don't try to resolve the (optional) module at build time.
    const moduleName = "flowise-components";
    const mod: unknown = await import(/* @vite-ignore */ moduleName).catch(() => undefined);
    const fn = (mod as { getCredentialData?: unknown } | undefined)?.getCredentialData;
    if (typeof fn === "function") {
      const data = await (fn as (id: string, opts: ICommonObject) => Promise<ICommonObject>)(
        credentialId,
        options
      );
      if (isObject(data)) return data;
    }
  } catch {
    /* standalone / module not present — fall through */
  }
  return undefined;
}
