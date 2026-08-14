import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(async () => ({ data: { session: { access_token: "test-token" } } })),
    },
  },
}));

import { calculateLimitation, generateDraft, listMatters, updateMatter } from "./api";

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as Response;
}

// FETCH_TIMEOUT_MS and TRANSIENT_RETRY_DELAYS_MS[0] in api.ts — kept in
// sync manually since they aren't exported (they're intentionally private
// retry-policy constants, not part of the module's public surface).
const FETCH_TIMEOUT_MS = 12000;
const FIRST_RETRY_DELAY_MS = 600;

describe("authedFetch retry policy", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("retries a GET after a transient 5xx and returns the eventual success", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(503, { detail: "upstream down" }))
      .mockResolvedValueOnce(jsonResponse(200, [{ id: "m1" }]));

    const promise = listMatters();
    await vi.advanceTimersByTimeAsync(FIRST_RETRY_DELAY_MS);
    await expect(promise).resolves.toEqual([{ id: "m1" }]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a non-idempotent write after an AbortController timeout", async () => {
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => {
          const err = new Error("The operation was aborted");
          err.name = "AbortError";
          reject(err);
        });
      });
    });

    const promise = generateDraft("matter-1", { template_id: "t1", form_data: {} });
    const assertion = expect(promise).rejects.toThrow();
    await vi.advanceTimersByTimeAsync(FETCH_TIMEOUT_MS);
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a non-idempotent write after a transient 5xx", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(503, { detail: "upstream down" }));

    await expect(
      generateDraft("matter-1", { template_id: "t1", form_data: {} })
    ).rejects.toThrow(/503/);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("still retries a de facto idempotent PATCH after a transient 5xx", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(503, { detail: "upstream down" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: "m1", title: "New Title" }));

    const promise = updateMatter("m1", { title: "New Title" });
    await vi.advanceTimersByTimeAsync(FIRST_RETRY_DELAY_MS);
    await expect(promise).resolves.toEqual({ id: "m1", title: "New Title" });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("still retries a deterministic/side-effect-free POST after a transient 5xx", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(503, { detail: "upstream down" }))
      .mockResolvedValueOnce(jsonResponse(200, { limitation_expiry_date: "2027-01-01" }));

    const promise = calculateLimitation({
      cause_of_action_date: "2024-01-01",
      suit_category: "contract",
    });
    await vi.advanceTimersByTimeAsync(FIRST_RETRY_DELAY_MS);
    await expect(promise).resolves.toEqual({ limitation_expiry_date: "2027-01-01" });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
