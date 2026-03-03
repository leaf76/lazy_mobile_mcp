import { describe, expect, it } from "vitest";
import { AppError, toErrorResponse } from "../src/errors.js";

describe("error format", () => {
  it("serializes to client-safe object", () => {
    const error = new AppError({
      message: "Device missing",
      code: "ERR_DEVICE_NOT_FOUND",
      category: "business",
      traceId: "trace-1"
    });

    expect(toErrorResponse(error)).toEqual({
      error: "Device missing",
      code: "ERR_DEVICE_NOT_FOUND",
      trace_id: "trace-1"
    });
  });
});
