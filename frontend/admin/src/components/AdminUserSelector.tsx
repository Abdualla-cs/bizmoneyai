"use client";

import { useDeferredValue, useMemo, useState } from "react";

import { AdminUserRow } from "@/lib/types";

type AdminUserSelectorProps = {
  users: AdminUserRow[];
  value: number | null;
  onChange: (value: number | null) => void;
  disabled?: boolean;
  loading?: boolean;
};

export default function AdminUserSelector({
  users,
  value,
  onChange,
  disabled = false,
  loading = false,
}: AdminUserSelectorProps) {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());

  const filteredUsers = useMemo(() => {
    if (!deferredSearch) {
      return users;
    }

    return users.filter((user) => `${user.name} ${user.email}`.toLowerCase().includes(deferredSearch));
  }, [deferredSearch, users]);

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search users"
          className="w-full bg-white xl:max-w-xs"
          disabled={disabled}
        />
      </div>

      <div className="flex max-h-72 flex-wrap gap-3 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50 p-3">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(null)}
          className={`min-h-[76px] min-w-[180px] rounded-2xl border px-4 py-3 text-left shadow-sm transition ${
            value === null
              ? "border-slate-950 bg-slate-950 text-white shadow-slate-300"
              : "border-slate-200 bg-white text-slate-900 hover:border-slate-300 hover:shadow-md"
          }`}
        >
          <span className="block text-sm font-semibold">All Users</span>
        </button>

        {filteredUsers.map((user) => {
          const isSelected = user.user_id === value;
          return (
            <button
              key={user.user_id}
              type="button"
              disabled={disabled}
              onClick={() => onChange(user.user_id)}
              className={`min-h-[76px] min-w-[190px] max-w-[240px] rounded-2xl border px-4 py-3 text-left shadow-sm transition ${
                isSelected
                  ? "border-teal-500 bg-teal-50 text-slate-950 shadow-teal-100 ring-2 ring-teal-500/20"
                  : "border-slate-200 bg-white text-slate-900 hover:border-teal-200 hover:bg-white hover:shadow-md"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <span className="block truncate text-sm font-semibold">{user.name}</span>
                  <span className="mt-1 block truncate text-xs text-slate-500">{user.email}</span>
                </div>
                <span
                  className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                    user.is_active ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                  aria-label={user.is_active ? "Active" : "Inactive"}
                />
              </div>
              <div className="mt-3 flex items-center justify-between text-xs">
                <span className={isSelected ? "font-semibold text-teal-700" : "text-slate-500"}>
                  {isSelected ? "Selected" : `${user.transactions_count} tx`}
                </span>
                <span className={isSelected ? "text-teal-700" : "text-slate-400"}>
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </button>
          );
        })}

        {filteredUsers.length === 0 && (
          <div className="flex min-h-[76px] flex-1 items-center rounded-2xl border border-dashed border-slate-300 bg-white px-4 text-sm text-slate-500">
            No users match this search.
          </div>
        )}
      </div>

      {loading && <p className="text-sm font-medium text-teal-700">Updating selected-user analytics...</p>}
      {!loading && users.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-sm text-slate-500">
          No users exist yet.
        </p>
      )}
    </div>
  );
}
