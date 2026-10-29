// Real API payloads captured from the dev data (tests/fixtures/dump_fixtures.py): T+90, T+105 and
// T+120 stream results, the BRAVO scene, the installations, the case graph known then and now,
// the diff, the shift delta, the explainer at T+90 and the eval report.
import type {
  DtwMsg,
  ExplainResponse,
  FeaturesMsg,
  ForecastMsg,
  HelloMsg,
  Installation,
  CaseSummary,
  MatchMsg,
  RecallMsg,
  Scene,
} from "../src/api/messages";
import type { CaseDiff, CaseGraph, EvalReport, HistoryPath, ShiftDeltaDoc } from "../src/api/pages";
import casesJ from "./fixtures/cases.json";
import deltaJ from "./fixtures/delta.json";
import diffJ from "./fixtures/diff.json";
import evalJ from "./fixtures/eval.json";
import explainJ from "./fixtures/explain_t090.json";
import nowJ from "./fixtures/graph_now.json";
import thenJ from "./fixtures/graph_then.json";
import historyJ from "./fixtures/history_delta.json";
import instJ from "./fixtures/installations.json";
import sceneJ from "./fixtures/scene_bravo.json";
import t090J from "./fixtures/t090.json";
import t105J from "./fixtures/t105.json";
import t120J from "./fixtures/t120.json";

function as<T>(v: unknown): T {
  return v as T;
}

export const T090 = as<{
  hello: HelloMsg;
  match: MatchMsg;
  forecast: ForecastMsg;
  dtw: DtwMsg;
  recall: RecallMsg;
  features: FeaturesMsg;
}>(t090J);
export const T105 = as<{ match: MatchMsg; forecast: ForecastMsg; features: FeaturesMsg }>(t105J);
export const T120 = as<{ match: MatchMsg; recall: RecallMsg; forecast: ForecastMsg }>(t120J);
export const SCENE = as<Scene>(sceneJ);
export const INSTALLATIONS = as<Installation[]>(instJ);
export const GRAPH_THEN = as<CaseGraph>(thenJ);
export const GRAPH_NOW = as<CaseGraph>(nowJ);
export const DIFF = as<CaseDiff>(diffJ);
export const DELTA = as<ShiftDeltaDoc>(deltaJ);
export const EXPLAIN = as<ExplainResponse>(explainJ);
export const HISTORY = as<HistoryPath>(historyJ);
export const CASES = as<CaseSummary[]>(casesJ);
export const EVAL = as<EvalReport>(evalJ);
