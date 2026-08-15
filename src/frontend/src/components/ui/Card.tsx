import React from "react";
import { cn } from "@/utils/cn";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
  glass?: boolean;
}

export const Card: React.FC<CardProps> = ({
  className,
  hoverable = false,
  glass = true,
  children,
  ...props
}) => {
  return (
    <div
      className={cn(
        "rounded-2xl border transition-all duration-300 overflow-hidden",
        glass
          ? "bg-slate-900/80 backdrop-blur-xl border-slate-800/80 shadow-xl shadow-black/20"
          : "bg-slate-900 border-slate-800 shadow-md",
        hoverable &&
          "hover:border-emerald-500/50 hover:shadow-emerald-500/5 hover:-translate-y-0.5 cursor-pointer",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={cn("p-5 border-b border-slate-800/80", className)} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  children,
  ...props
}) => (
  <h3 className={cn("text-lg font-bold text-slate-100 tracking-tight", className)} {...props}>
    {children}
  </h3>
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={cn("p-5", className)} {...props}>
    {children}
  </div>
);

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={cn("p-5 border-t border-slate-800/80 bg-slate-950/40", className)} {...props}>
    {children}
  </div>
);
