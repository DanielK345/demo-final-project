import React from "react";
import { cn } from "@/utils/cn";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "circular" | "rectangular";
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = "rectangular",
  ...props
}) => {
  const variantStyles = {
    text: "h-4 w-full rounded-md",
    circular: "rounded-full",
    rectangular: "rounded-xl",
  };

  return (
    <div
      className={cn(
        "animate-pulse bg-slate-800/80 border border-slate-700/30",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
};
