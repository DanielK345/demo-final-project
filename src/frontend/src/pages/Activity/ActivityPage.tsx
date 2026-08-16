import React, { useState } from "react";
import { ActivityList } from "@/features/activity/components/ActivityList";

export const ActivityPage: React.FC = () => {
  const [filter, setFilter] = useState<string>("all");

  const filterChips = [
    { id: "all", label: "Tất cả" },
    { id: "recent", label: "Gần đây" },
    { id: "last_month", label: "Tháng trước" },
    { id: "cancelled", label: "Đã hủy" },
  ];

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6 pb-12">
      {/* Page Title */}
      <h1 className="text-3xl font-extrabold text-[#191C1E] dark:text-white tracking-tight">
        Lịch sử chuyến đi
      </h1>

      {/* Horizontal Filter Chips */}
      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-2">
        {filterChips.map((chip) => {
          const isActive = filter === chip.id;
          return (
            <button
              key={chip.id}
              onClick={() => setFilter(chip.id)}
              className={`shrink-0 px-5 py-2 rounded-full text-xs font-semibold transition-all duration-200 cursor-pointer ${
                isActive
                  ? "bg-[#00A651] text-white shadow-xs"
                  : "bg-slate-200/80 text-slate-700 hover:bg-slate-300 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/20"
              }`}
            >
              {chip.label}
            </button>
          );
        })}
      </div>

      {/* Trip Cards List */}
      <ActivityList activeFilter={filter} />
    </div>
  );
};
