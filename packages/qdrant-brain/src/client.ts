import { z } from "zod";
import { getQdrantEnv, type QdrantEnv } from "./env.js";

export type QdrantConfig = QdrantEnv;

export interface QdrantRequestInput {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
  json?: unknown;
}

export function getQdrantConfig(): QdrantConfig {
  return getQdrantEnv();
}

function qdrantUrl(path: string, query?: QdrantRequestInput["query"]): string {
  const config = getQdrantConfig();
  const base = config.QDRANT_URL.replace(/\/+$/, "");
  const url = new URL(`${base}${path.startsWith("/") ? path : `/${path}`}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  return url.toString();
}

export async function qdrantRequest<T>(schema: z.ZodType<T>, input: QdrantRequestInput): Promise<T> {
  const config = getQdrantConfig();
  const init: RequestInit = {
    method: input.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(config.QDRANT_API_KEY ? { "api-key": config.QDRANT_API_KEY } : {})
    }
  };
  if (input.json !== undefined) {
    init.body = JSON.stringify(input.json);
  }
  const response = await fetch(qdrantUrl(input.path, input.query), init);
  const text = await response.text();
  const parsedBody = text.length > 0 ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Qdrant ${input.method ?? "GET"} ${input.path} failed with ${response.status}: ${text}`);
  }
  return schema.parse(parsedBody);
}

export async function waitForQdrantReady(input: {
  attempts?: number;
  delayMs?: number;
  onRetry?: (attempt: number, message: string) => void;
} = {}): Promise<void> {
  const attempts = input.attempts ?? 60;
  const delayMs = input.delayMs ?? 1000;
  let last = "not checked";
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await qdrantRequest(z.record(z.unknown()), { path: "/" });
      return;
    } catch (error: unknown) {
      last = error instanceof Error ? error.message : String(error);
      input.onRetry?.(attempt, last);
      await new Promise((resolve) => {
        setTimeout(resolve, delayMs);
      });
    }
  }
  throw new Error(`Qdrant did not become ready: ${last}`);
}

export function describeQdrantEndpoints(): { url: string; collection: string } {
  const config = getQdrantConfig();
  return { url: config.QDRANT_URL, collection: config.QDRANT_COLLECTION };
}
