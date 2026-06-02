import {
  executeRemediationDefinition,
  queryQdrantMemoryDefinition,
  operaiqGetRunbookDefinition,
  operaiqGetServiceDependencyGraphDefinition,
  operaiqSearchSimilarIncidentsDefinition,
  operaiqWritePostmortemDefinition
} from "./tools/index.js";
import type { AgentToolDefinition } from "./tool-json-schemas.js";

export const operaiqToolDefinitions: AgentToolDefinition[] = [
  operaiqSearchSimilarIncidentsDefinition,
  queryQdrantMemoryDefinition,
  operaiqGetServiceDependencyGraphDefinition,
  operaiqGetRunbookDefinition,
  executeRemediationDefinition,
  operaiqWritePostmortemDefinition
];
