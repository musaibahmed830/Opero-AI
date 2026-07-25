import { API_BASE_URL } from "@/lib/config";

const TOKEN_KEY = "opero_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body.detail ?? body);
  } catch {
    return response.statusText;
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export interface AuthUser {
  id: string;
  email: string;
  organization_id: string;
}

export async function login(email: string, password: string): Promise<void> {
  const { access_token } = await apiFetch<{ access_token: string }>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(access_token);
}

export async function register(
  organizationName: string,
  email: string,
  password: string,
): Promise<void> {
  const { access_token } = await apiFetch<{ access_token: string }>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ organization_name: organizationName, email, password }),
  });
  setToken(access_token);
}

export async function getCurrentUser(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/v1/auth/me");
}

export function logout(): void {
  clearToken();
}
