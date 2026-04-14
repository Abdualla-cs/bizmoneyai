"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import api from "@/lib/api";
import { getErrorMessage, getStatusCode } from "@/lib/errors";
import { AdminSortOrder } from "@/lib/types";

type QueryParamValue = string | number | boolean | undefined;

type UseAdminDataTableOptions<Response, Row> = {
  queryKey: string;
  endpoint: string;
  extractRows: (response: Response) => Row[];
  extractTotal: (response: Response) => number;
  staticParams?: Record<string, QueryParamValue>;
  initialFilters?: Record<string, string>;
  initialLimit?: number;
  defaultSort?: { key: string; order: AdminSortOrder };
  searchParam?: string | false;
  errorMessage: string;
};

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedValue(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs, value]);

  return debouncedValue;
}

export function useAdminDataTable<Response, Row>({
  queryKey,
  endpoint,
  extractRows,
  extractTotal,
  staticParams,
  initialFilters,
  initialLimit = 10,
  defaultSort,
  searchParam = "search",
  errorMessage,
}: UseAdminDataTableOptions<Response, Row>) {
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>(initialFilters ?? {});
  const [limit, setLimit] = useState(initialLimit);
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState(defaultSort?.key ?? "");
  const [sortOrder, setSortOrder] = useState<AdminSortOrder>(defaultSort?.order ?? "desc");

  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const serializedFilters = JSON.stringify(filters);
  const serializedStaticParams = JSON.stringify(staticParams ?? {});

  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, serializedFilters, limit]);

  const params = useMemo(() => {
    const merged: Record<string, QueryParamValue> = {
      ...(staticParams ?? {}),
      limit,
      offset,
      sort_by: sortBy || undefined,
      sort_order: sortOrder,
    };

    if (searchParam !== false) {
      merged[searchParam] = debouncedSearch || undefined;
    }

    Object.entries(filters).forEach(([key, value]) => {
      merged[key] = value || undefined;
    });

    return merged;
  }, [debouncedSearch, filters, limit, offset, searchParam, serializedStaticParams, sortBy, sortOrder, staticParams]);

  const query = useQuery({
    queryKey: [queryKey, params],
    queryFn: async ({ signal }) => {
      const response = await api.get<Response>(endpoint, { params, signal });
      return response.data;
    },
    placeholderData: keepPreviousData,
  });

  const error =
    query.error && getStatusCode(query.error) !== 401 && getStatusCode(query.error) !== 403
      ? getErrorMessage(query.error, errorMessage)
      : "";

  const rows = query.data ? extractRows(query.data) : [];
  const total = query.data ? extractTotal(query.data) : 0;
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  const updateFilter = (key: string, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const updateSort = (key: string) => {
    if (sortBy === key) {
      setSortOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setSortOrder("asc");
    }
    setOffset(0);
  };

  const setPage = (page: number) => {
    const nextPage = Math.max(1, Math.min(totalPages, page));
    setOffset((nextPage - 1) * limit);
  };

  const setPageSize = (pageSize: number) => {
    setLimit(pageSize);
    setOffset(0);
  };

  return {
    data: query.data,
    rows,
    total,
    error,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    refetch: query.refetch,
    search,
    setSearch,
    filters,
    setFilter: updateFilter,
    limit,
    setPageSize,
    offset,
    currentPage,
    totalPages,
    setPage,
    sortBy,
    sortOrder,
    setSort: updateSort,
  };
}
