export type ErrorCategory = "validation" | "business" | "dependency" | "system";

export interface ErrorResponse {
  error: string;
  code: string;
  trace_id: string;
}

export interface AppErrorOptions {
  message: string;
  code: string;
  category: ErrorCategory;
  traceId: string;
  cause?: unknown;
}

export class AppError extends Error {
  readonly code: string;
  readonly category: ErrorCategory;
  readonly traceId: string;

  constructor(options: AppErrorOptions) {
    super(options.message, { cause: options.cause });
    this.name = "AppError";
    this.code = options.code;
    this.category = options.category;
    this.traceId = options.traceId;
  }
}

export function toErrorResponse(error: AppError): ErrorResponse {
  return {
    error: error.message,
    code: error.code,
    trace_id: error.traceId
  };
}

export function normalizeError(error: unknown, traceId: string): AppError {
  if (error instanceof AppError) {
    return error;
  }

  if (error instanceof Error) {
    return new AppError({
      message: error.message,
      code: "ERR_INTERNAL",
      category: "system",
      traceId,
      cause: error
    });
  }

  return new AppError({
    message: "Unknown server error",
    code: "ERR_INTERNAL",
    category: "system",
    traceId
  });
}
