export type At = string;
export type RunId = string;
export type Seq = number;
export type Type =
  | "run.status"
  | "task.started"
  | "task.finished"
  | "model.completed"
  | "tool.called"
  | "tool.result"
  | "run.finished"
  | "model.delta";
export type V = 1;

/**
 * SSE `data` 봉투(2.7). `seq` 는 Run 안에서 1 부터 단조 증가합니다.
 */
export interface RunEvent {
  at: At;
  payload: Payload;
  run_id: RunId;
  seq: Seq;
  type: Type;
  v?: V;
  [k: string]: unknown;
}
export interface Payload {
  [k: string]: unknown;
}
