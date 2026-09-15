/**
 * spec 0002 2.7, 2.17, D-4, C-4: SSE 파서 — `fetch` 가 돌려주는 `text/event-stream`
 * 본문(`ReadableStream<Uint8Array>`)을 `{ id?, event?, data }` 이벤트로 파싱합니다.
 *
 * 브라우저 `EventSource` 를 쓰지 않는 이유는 `Authorization` 헤더를 붙일 수 없기
 * 때문입니다(C-4) — `client.ts` 의 `streamRunEvents` 가 `fetch` 로 연 스트림을 이
 * 파서에 넘깁니다.
 *
 * WHATWG SSE 필드 파싱 규칙을 따릅니다: `field: value` 에서 콜론 바로 뒤 공백
 * 하나만 제거합니다(그 뒤 공백은 값의 일부). `data:` 가 여러 줄이면 `\n` 으로
 * 이어 붙입니다(멀티라인, 2.7 은 실제로는 압축 JSON 한 줄만 보내지만 파서는
 * 계약대로 멀티라인을 지원합니다). 빈 줄이 이벤트 하나의 끝이고, 그때까지 모은
 * `data` 가 없으면(연속 빈 줄 등) 이벤트를 내지 않습니다. `\r\n`·`\n` 모두 줄
 * 구분자로 허용합니다.
 */

export interface SseEvent {
  id?: string;
  event?: string;
  data: string;
}

function splitField(line: string): { field: string; value: string } {
  const colonIndex = line.indexOf(":");
  if (colonIndex === -1) {
    return { field: line, value: "" };
  }
  const field = line.slice(0, colonIndex);
  let value = line.slice(colonIndex + 1);
  if (value.startsWith(" ")) {
    value = value.slice(1);
  }
  return { field, value };
}

function abortError(): DOMException {
  return new DOMException("This operation was aborted", "AbortError");
}

/**
 * `stream` 을 SSE 이벤트로 파싱합니다. `signal` 이 주어지고 중단되면 진행 중인
 * 읽기를 취소하고(`ReadableStreamDefaultReader.cancel`) `AbortError` 로 끝냅니다
 * — `streamRunEvents` 가 이 신호로 `Last-Event-ID` 재접속 여부를 호출부에 맡깁니다.
 */
export async function* parseSse(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent, void, void> {
  if (signal?.aborted) {
    throw abortError();
  }

  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  let id: string | undefined;
  let eventType: string | undefined;
  let dataLines: string[] = [];

  const resetPending = (): void => {
    id = undefined;
    eventType = undefined;
    dataLines = [];
  };

  const onAbort = (): void => {
    reader.cancel(signal?.reason).catch(() => {
      // 취소 자체의 실패는 무시합니다 — 아래 read() 루프가 signal.aborted 를 보고 끝냅니다.
    });
  };
  signal?.addEventListener("abort", onAbort);

  try {
    while (true) {
      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await reader.read();
      } catch (error) {
        if (signal?.aborted) {
          throw abortError();
        }
        throw error;
      }

      if (signal?.aborted) {
        throw abortError();
      }

      if (result.done) {
        break;
      }

      buffer += decoder.decode(result.value, { stream: true });

      let newlineIndex = buffer.indexOf("\n");
      while (newlineIndex !== -1) {
        let line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);
        if (line.endsWith("\r")) {
          line = line.slice(0, -1);
        }

        if (line === "") {
          if (dataLines.length > 0) {
            yield { id, event: eventType, data: dataLines.join("\n") };
          }
          resetPending();
        } else {
          const { field, value } = splitField(line);
          if (field === "id") {
            id = value;
          } else if (field === "event") {
            eventType = value;
          } else if (field === "data") {
            dataLines.push(value);
          }
          // 그 밖의 필드(`retry:`, 주석 `:...`)는 이 sdk 가 쓰지 않아 무시합니다.
        }

        newlineIndex = buffer.indexOf("\n");
      }
    }

    if (dataLines.length > 0) {
      yield { id, event: eventType, data: dataLines.join("\n") };
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
    reader.releaseLock();
  }
}
