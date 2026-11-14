export type FieldError = {
  loc: (string | number)[];
  msg: string;
  type: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | FieldError[] | null;

  constructor(status: number, detail: string | FieldError[] | null) {
    super(`API answered ${String(status)}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const VALUE_ERROR = "Value error, ";

function withoutPrefix(message: string): string {
  return message.startsWith(VALUE_ERROR)
    ? message.slice(VALUE_ERROR.length)
    : message;
}

export function fieldErrors(error: ApiError): {
  fields: Record<string, string>;
  form: string | null;
} {
  const fields: Record<string, string> = {};
  if (typeof error.detail === "string") return { fields, form: error.detail };
  let form: string | null = null;
  for (const { loc, msg } of error.detail ?? []) {
    const message = withoutPrefix(msg);
    const field = loc.length > 1 ? loc.at(-1) : undefined;
    if (field === undefined) {
      form ??= message;
    } else {
      fields[String(field)] ??= message;
    }
  }
  return { fields, form };
}

export function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return "You don't have permission to do this.";
    if (error.status === 404) {
      return "This page does not exist. Check the address or go back to your projects.";
    }
  }
  return "Something went wrong. Try again.";
}
