import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

/**
 * Small button with a few variants:
 *   variant: "primary" | "default" | "ghost"
 *   size:    "sm" | "md"
 *   loading: shows a spinner and disables the button
 */
export default function Button({
  variant = "default",
  size = "md",
  loading = false,
  className,
  children,
  ...rest
}) {
  const variants = {
    primary:
      "bg-brand-500 text-white hover:bg-brand-400 border border-brand-500 shadow-sm shadow-brand-500/20",
    default:
      "bg-ink-750 text-ink-100 border border-line hover:border-brand-500/60 hover:bg-ink-700",
    ghost: "bg-transparent text-ink-200 border border-transparent hover:bg-white/5",
  };
  const sizes = {
    sm: "px-3 py-1.5 text-xs gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg font-medium transition-colors",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading && <Loader2 size={16} className="animate-spin" />}
      {children}
    </button>
  );
}
