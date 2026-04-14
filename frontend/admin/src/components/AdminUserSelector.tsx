"use client";

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

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
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());

  const selectedUser = useMemo(
    () => users.find((user) => user.user_id === value) ?? null,
    [users, value],
  );

  const filteredUsers = useMemo(() => {
    if (!deferredSearch) {
      return users;
    }

    return users.filter((user) => `${user.name} ${user.email}`.toLowerCase().includes(deferredSearch));
  }, [deferredSearch, users]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        setSearch("");
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const closeMenu = () => {
    setOpen(false);
    setSearch("");
  };

  const selectUser = (nextUserId: number | null) => {
    onChange(nextUserId);
    closeMenu();
  };

  const summaryLabel = selectedUser ? selectedUser.name : "All users";
  const summaryDescription = selectedUser
    ? selectedUser.email
    : "Global system analytics across every user account";

  return (
    <div ref={containerRef} className="relative">
      <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-[0.22em] text-slate-500">
        <span>Analytics Scope</span>
        <span>{selectedUser ? "User view" : "Global view"}</span>
      </div>

      <button
        type="button"
        disabled={disabled}
        aria-expanded={open.toString()}
        aria-haspopup="listbox"
        onClick={() => {
          if (!disabled) {
            setOpen((current) => !current);
          }
        }}
        className="flex w-full items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-slate-900 shadow-sm transition hover:border-slate-300 hover:shadow-md"
      >
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{summaryLabel}</p>
          <p className="truncate text-sm text-slate-500">{summaryDescription}</p>
        </div>
        <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
          {loading ? "Updating" : open ? "Close" : "Select"}
        </span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 z-20 mt-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl">
          <input
            value={search}
            autoFocus
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search users by name or email"
            className="w-full bg-white"
          />

          <ul role="listbox" className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
            <li role="option" aria-selected={value === null}>
              <button
                type="button"
                onClick={() => selectUser(null)}
                className={`w-full rounded-xl border px-4 py-3 text-left transition ${value === null
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-white text-slate-900 hover:border-slate-300 hover:bg-slate-50"
                  }`}
              >
                <p className="text-sm font-semibold">All users</p>
                <p className={`text-sm ${value === null ? "text-slate-200" : "text-slate-500"}`}>
                  Show the current global system analytics view
                </p>
              </button>
            </li>

            {filteredUsers.length > 0 ? (
              filteredUsers.map((user) => {
                const isSelected = user.user_id === value;

                return (
                  <li key={user.user_id} role="option" aria-selected={isSelected}>
                    <button
                      type="button"
                      onClick={() => selectUser(user.user_id)}
                      className={`w-full rounded-xl border px-4 py-3 text-left transition ${isSelected
                          ? "border-teal-500 bg-teal-50 text-slate-900"
                          : "border-slate-200 bg-white text-slate-900 hover:border-slate-300 hover:bg-slate-50"
                        }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold">{user.name}</p>
                          <p className="truncate text-sm text-slate-500">{user.email}</p>
                        </div>
                        {isSelected && (
                          <span className="rounded-full bg-teal-600 px-2.5 py-1 text-[11px] font-semibold text-white">
                            Selected
                          </span>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })
            ) : (
              <li className="px-2 py-4 text-sm text-slate-500">No users match your search.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
