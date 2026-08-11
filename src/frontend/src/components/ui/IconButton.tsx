import React from "react";
import { cn } from "@/utils/cn";

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
  icon: React.ReactNode;
  label: string;
}

export const IconButton: React.FC<IconButtonProps> = ({
  className,
  variant = "ghost",
  size = "md",
  icon,
  label,
  ...props
}) => {
  const variantStyles = {
    primary: "bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20",
    secondary: "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/60",
    outline: "bg-transparent border border-slate-700 hover:border-slate-500 text-slate-300",
    ghost: "bg-transparent hover:bg-slate-800/80 text-slate-400 hover:text-slate-100",
  };

  const sizeStyles = {
    sm: "p-1.5 rounded-lg",
    md: "p-2.5 rounded-xl",
    lg: "p-3 rounded-2xl",
  };

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex items-center justify-center transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {icon}
    </button>
  );
};
