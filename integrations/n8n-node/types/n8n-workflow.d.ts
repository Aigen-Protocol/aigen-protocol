/**
 * Ambient declaration of the subset of the `n8n-workflow` SDK used by this
 * community-node package.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * n8n community nodes import their types from the `n8n-workflow` package, which
 * is provided by the n8n host at runtime (it is a `peerDependency`, never bundled
 * by a community node). To keep this package type-checkable in isolation — i.e.
 * so `tsc --noEmit` passes without installing the full n8n monorepo — we declare
 * here exactly the interfaces our nodes and credential touch.
 *
 * These signatures are faithful to the public n8n API (`INodeType`,
 * `INodeTypeDescription`, `IExecuteFunctions`, `IPollFunctions`,
 * `ICredentialType`, `IHttpRequestOptions`, …). When this package is installed
 * into a real n8n instance the genuine `n8n-workflow` types take over and the
 * node code compiles unchanged against them; the broader real types are a strict
 * superset of what we declare, so nothing here conflicts.
 *
 * This file contains NO runtime code — it is purely `declare module`.
 */

declare module 'n8n-workflow' {
  // ---------------------------------------------------------------------------
  // Primitive JSON shapes
  // ---------------------------------------------------------------------------

  export type GenericValue = string | object | number | boolean | undefined | null;

  export interface IDataObject {
    [key: string]: GenericValue | IDataObject | GenericValue[] | IDataObject[];
  }

  export type NodeParameterValue = string | number | boolean | undefined | null;

  export interface INodeParameters {
    [key: string]: NodeParameterValueType;
  }

  export type NodeParameterValueType =
    | NodeParameterValue
    | INodeParameters
    | INodeParameterResourceLocator
    | NodeParameterValue[]
    | INodeParameters[];

  export interface INodeParameterResourceLocator {
    __rl: true;
    mode: string;
    value: NodeParameterValue;
    cachedResultName?: string;
  }

  // ---------------------------------------------------------------------------
  // Execution data envelope
  // ---------------------------------------------------------------------------

  export interface IBinaryData {
    data: string;
    mimeType: string;
    fileName?: string;
    [key: string]: string | undefined;
  }

  export interface IBinaryKeyData {
    [key: string]: IBinaryData;
  }

  export interface IPairedItemData {
    item: number;
    input?: number;
  }

  export interface INodeExecutionData {
    json: IDataObject;
    binary?: IBinaryKeyData;
    error?: NodeApiError | NodeOperationError;
    pairedItem?: IPairedItemData | IPairedItemData[] | number;
    [key: string]: unknown;
  }

  // ---------------------------------------------------------------------------
  // HTTP helper (this.helpers.httpRequest / httpRequestWithAuthentication)
  // ---------------------------------------------------------------------------

  export type IHttpRequestMethods =
    | 'GET'
    | 'POST'
    | 'PUT'
    | 'PATCH'
    | 'DELETE'
    | 'HEAD'
    | 'OPTIONS';

  export interface IHttpRequestOptions {
    url: string;
    baseURL?: string;
    method?: IHttpRequestMethods;
    body?: IDataObject | Uint8Array | string | unknown;
    qs?: IDataObject;
    headers?: Record<string, string>;
    auth?: { username: string; password: string };
    json?: boolean;
    returnFullResponse?: boolean;
    encoding?: 'arraybuffer' | 'text' | 'json' | 'stream';
    timeout?: number;
    ignoreHttpStatusErrors?: boolean;
    skipSslCertificateValidation?: boolean;
  }

  export interface IRequestOptions {
    [key: string]: unknown;
  }

  export interface IN8nHttpFullResponse {
    body: unknown;
    headers: Record<string, string | string[] | undefined>;
    statusCode: number;
    statusMessage?: string;
  }

  export interface IHttpRequestHelper {
    httpRequest(requestOptions: IHttpRequestOptions): Promise<unknown>;
    httpRequestWithAuthentication(
      credentialsType: string,
      requestOptions: IHttpRequestOptions,
      additionalCredentialOptions?: IDataObject,
    ): Promise<unknown>;
    returnJsonArray(jsonData: IDataObject | IDataObject[]): INodeExecutionData[];
    prepareBinaryData(
      binaryData: Uint8Array,
      filePath?: string,
      mimeType?: string,
    ): Promise<IBinaryData>;
  }

  // ---------------------------------------------------------------------------
  // Credentials
  // ---------------------------------------------------------------------------

  export interface ICredentialDataDecryptedObject {
    [key: string]: GenericValue | IDataObject;
  }

  export interface IAuthenticateGeneric {
    type: 'generic';
    properties: {
      headers?: Record<string, string>;
      qs?: Record<string, string>;
      body?: IDataObject;
      auth?: { username: string; password: string };
    };
  }

  export type IAuthenticate = IAuthenticateGeneric;

  export interface ICredentialTestRequest {
    request: {
      baseURL?: string;
      url: string;
      method?: IHttpRequestMethods;
      headers?: Record<string, string>;
      qs?: IDataObject;
    };
    rules?: Array<{
      type: 'responseSuccessBody' | 'responseCode';
      properties: Record<string, unknown>;
    }>;
  }

  export interface ICredentialType {
    name: string;
    displayName: string;
    documentationUrl?: string;
    icon?: string;
    iconUrl?: string;
    extends?: string[];
    properties: INodeProperties[];
    authenticate?: IAuthenticate;
    test?: ICredentialTestRequest;
  }

  // ---------------------------------------------------------------------------
  // Node property descriptors (INodeTypeDescription.properties)
  // ---------------------------------------------------------------------------

  export type NodePropertyTypes =
    | 'boolean'
    | 'collection'
    | 'color'
    | 'dateTime'
    | 'fixedCollection'
    | 'hidden'
    | 'json'
    | 'notice'
    | 'multiOptions'
    | 'number'
    | 'options'
    | 'string'
    | 'credentialsSelect'
    | 'resourceLocator';

  export interface INodePropertyOptions {
    name: string;
    value: string | number | boolean;
    description?: string;
    action?: string;
    routing?: IDataObject;
  }

  export interface IDisplayOptions {
    show?: { [key: string]: Array<string | number | boolean> | undefined };
    hide?: { [key: string]: Array<string | number | boolean> | undefined };
  }

  export interface INodePropertyTypeOptions {
    minValue?: number;
    maxValue?: number;
    numberPrecision?: number;
    multipleValues?: boolean;
    multipleValueButtonText?: string;
    rows?: number;
    password?: boolean;
    loadOptionsMethod?: string;
    [key: string]: unknown;
  }

  export interface INodeProperties {
    displayName: string;
    name: string;
    type: NodePropertyTypes;
    default: NodeParameterValueType;
    description?: string;
    hint?: string;
    required?: boolean;
    noDataExpression?: boolean;
    placeholder?: string;
    options?: Array<INodePropertyOptions | INodeProperties | INodePropertyCollection>;
    displayOptions?: IDisplayOptions;
    typeOptions?: INodePropertyTypeOptions;
    routing?: IDataObject;
  }

  export interface INodePropertyCollection {
    displayName: string;
    name: string;
    values: INodeProperties[];
  }

  // ---------------------------------------------------------------------------
  // Node type description + node type
  // ---------------------------------------------------------------------------

  export type NodeConnectionType =
    | 'main'
    | 'ai_agent'
    | 'ai_tool'
    | 'ai_languageModel'
    | string;

  export interface INodeCredentialDescription {
    name: string;
    required?: boolean;
    displayOptions?: IDisplayOptions;
    testedBy?: string;
  }

  export interface ICredentialTestFunctions {
    helpers: IHttpRequestHelper;
  }

  export interface INodeTypeDescription {
    displayName: string;
    name: string;
    icon?: string | { light: string; dark: string };
    group: string[];
    version: number | number[];
    subtitle?: string;
    description: string;
    defaults: { name: string; color?: string };
    inputs: NodeConnectionType[] | string[];
    outputs: NodeConnectionType[] | string[];
    credentials?: INodeCredentialDescription[];
    requestDefaults?: {
      baseURL?: string;
      url?: string;
      headers?: Record<string, string>;
    };
    polling?: boolean;
    properties: INodeProperties[];
    documentationUrl?: string;
    codex?: IDataObject;
  }

  // ---------------------------------------------------------------------------
  // Execution contexts
  // ---------------------------------------------------------------------------

  export interface IGetNodeParameterOptions {
    extractValue?: boolean;
  }

  export interface IWorkflowDataProxyData {
    [key: string]: unknown;
  }

  export interface IExecuteFunctions {
    getInputData(inputIndex?: number): INodeExecutionData[];
    getNodeParameter(
      parameterName: string,
      itemIndex: number,
      fallbackValue?: NodeParameterValueType,
      options?: IGetNodeParameterOptions,
    ): NodeParameterValueType | object;
    getCredentials<T extends object = ICredentialDataDecryptedObject>(
      type: string,
      itemIndex?: number,
    ): Promise<T>;
    getNode(): INode;
    continueOnFail(): boolean;
    helpers: IHttpRequestHelper;
    logger: Logger;
  }

  export interface IPollFunctions {
    getNodeParameter(
      parameterName: string,
      fallbackValue?: NodeParameterValueType,
      options?: IGetNodeParameterOptions,
    ): NodeParameterValueType | object;
    getCredentials<T extends object = ICredentialDataDecryptedObject>(
      type: string,
    ): Promise<T>;
    getNode(): INode;
    getMode(): 'manual' | 'trigger';
    getWorkflowStaticData(type: 'global' | 'node'): IDataObject;
    helpers: IHttpRequestHelper;
    logger: Logger;
  }

  export interface INode {
    id: string;
    name: string;
    type: string;
    typeVersion: number;
    parameters: INodeParameters;
  }

  export interface Logger {
    debug(message: string, meta?: object): void;
    info(message: string, meta?: object): void;
    warn(message: string, meta?: object): void;
    error(message: string, meta?: object): void;
  }

  // ---------------------------------------------------------------------------
  // Node interface (regular node + trigger/poll node)
  // ---------------------------------------------------------------------------

  export interface INodeType {
    description: INodeTypeDescription;
    execute?(this: IExecuteFunctions): Promise<INodeExecutionData[][]>;
    poll?(this: IPollFunctions): Promise<INodeExecutionData[][] | null>;
    methods?: {
      credentialTest?: {
        [key: string]: (this: ICredentialTestFunctions, ...args: unknown[]) => Promise<unknown>;
      };
    };
  }

  // ---------------------------------------------------------------------------
  // Errors
  // ---------------------------------------------------------------------------

  export interface INodeErrorOptions {
    message?: string;
    description?: string;
    itemIndex?: number;
    runIndex?: number;
    httpCode?: string;
  }

  export class NodeOperationError extends Error {
    constructor(node: INode, error: Error | string, options?: INodeErrorOptions);
    description?: string | null;
    context: IDataObject;
  }

  export class NodeApiError extends Error {
    constructor(node: INode, error: IDataObject | Error, options?: INodeErrorOptions);
    description?: string | null;
    httpCode?: string | null;
    context: IDataObject;
  }

  export const jsonParse: <T = unknown>(jsonString: string, options?: { errorMessage?: string }) => T;
}
