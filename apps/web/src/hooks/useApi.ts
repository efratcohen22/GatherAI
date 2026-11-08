import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { useToast } from "@/components/ui";
import { api } from "@/lib/api";

export const useGet = <T,>(path: string, enabled = true) => useQuery({ queryKey: [path], queryFn: () => api<T>(path), enabled });

export function useEventId(): string {
  return useParams().eventId as string;
}

interface Call { path: string; method?: string; body?: unknown }

/** Runs one API call, refreshes all server data, and reports the outcome. */
export function useAction<T = unknown>(successMessage?: string) {
  const client = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ path, method = "POST", body }: Call) => api<T>(path, method, body),
    onSuccess: () => {
      client.invalidateQueries();
      if (successMessage) toast("success", successMessage);
    },
    onError: (error: Error) => toast("error", error.message),
  });
}
