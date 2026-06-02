import { z } from "zod";

export const qdrantRecordSchema = z.record(z.unknown()).and(z.object({ _key: z.string().optional() }).passthrough());
export type QdrantRecord = z.infer<typeof qdrantRecordSchema>;

export const qdrantSearchResultSchema = z.record(z.unknown());
export type QdrantSearchResult = z.infer<typeof qdrantSearchResultSchema>;

export const qdrantEventSchema = z.record(z.unknown());
export type QdrantEvent = z.infer<typeof qdrantEventSchema>;

export interface QdrantMemoryEvent {
  time?: number;
  host?: string;
  source?: string;
  eventType?: string;
  namespace?: string;
  fields?: Record<string, string | number | boolean>;
  event: Record<string, unknown>;
}

export interface SimilarIncident {
  id: string;
  title: string;
  rootCause: string | null;
  resolution: string | null;
  remediationSteps: string[];
  durationMinutes: number | null;
  severity: string;
  similarity: number;
}
