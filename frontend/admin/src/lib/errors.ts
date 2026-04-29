import { isAxiosError } from "axios";

export function getErrorMessage(error: unknown, fallback: string) {
  if (isAxiosError(error) && typeof error.response?.data?.detail === "string") {
    return error.response.data.detail;
  }
  return fallback;
}

export function getStatusCode(error: unknown) {
  if (isAxiosError(error)) {
    return error.response?.status ?? null;
  }
  return null;
}
