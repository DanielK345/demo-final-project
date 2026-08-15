import React from "react";
import { cn } from "@/utils/cn";

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string;
  name?: string;
  size?: "sm" | "md" | "lg" | "xl";
}

export const Avatar: React.FC<AvatarProps> = ({
  src,
  name = "User",
  size = "md",
  className,
  ...props
}) => {
  const [imageError, setImageError] = React.useState(false);

  const getInitials = (n: string) => {
    return n
      .split(" ")
      .map((part) => part[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const sizeStyles = {
    sm: "w-8 h-8 text-xs",
    md: "w-10 h-10 text-sm",
    lg: "w-12 h-12 text-base",
    xl: "w-16 h-16 text-lg font-bold",
  };

  return (
    <div
      className={cn(
        "relative inline-flex items-center justify-center rounded-full overflow-hidden bg-gradient-to-br from-emerald-600 to-cyan-700 text-white font-semibold shadow-inner shrink-0 border border-slate-700/50 select-none",
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {src && !imageError ? (
        <img
          src={src}
          alt={name}
          className="w-full h-full object-cover"
          onError={() => setImageError(true)}
        />
      ) : (
        <span>{getInitials(name)}</span>
      )}
    </div>
  );
};
