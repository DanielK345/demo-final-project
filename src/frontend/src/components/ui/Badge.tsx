import React from "react";
import { cn } from "@/utils/cn";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "success" | "warning" | "info" | "danger" | "neutral";
  size?: "sm" | "md";
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = "neutral",
  size = "md",
  children,
  ...props
}) => {
  const variantStyles = {
    success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    info: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
    danger: "bg-rose-500/10 text-rose-400 border-rose-500/30",
    neutral: "bg-slate-800 text-slate-300 border-slate-700",
  };

  const sizeStyles = {
    sm: "text-[10px] px-2 py-0.5 font-semibold tracking-wider",
    md: "text-xs px-2.5 py-1 font-medium",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border uppercase tracking-wider select-none",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
