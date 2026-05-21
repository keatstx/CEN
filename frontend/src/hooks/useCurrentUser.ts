import { useEffect, useState } from "react";

import { fetchCurrentUser } from "../api";
import type { User } from "../types";

/**
 * Fetches the current user once on mount and caches the result.
 *
 * Returns `{ user, loading, error }`. `user` is `null` while loading or
 * if the fetch fails (network down / 401). Callers should treat
 * `is_admin: false` as the safe default when `user === null`.
 *
 * Replace with a real auth-context provider when RBAC + real auth land.
 */
export function useCurrentUser(): {
  user: User | null;
  loading: boolean;
  error: string | null;
} {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCurrentUser()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Failed to load user");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, loading, error };
}
