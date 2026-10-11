import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium leading-none", {
  variants: {
    tone: {
      neutral: "border-border text-muted",
      ok: "border-ok/50 text-ok",
      warn: "border-warn/50 text-warn",
      err: "border-err/50 text-err",
      accent: "border-accent/50 text-accent",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
