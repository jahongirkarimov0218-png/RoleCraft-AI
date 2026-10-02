import React from "react";
import {
  AlertCircle,
  WifiOff,
  ServerCrash,
  AlertTriangle,
  RotateCw,
  X,
  LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type ErrorType =
  | "validation"
  | "network"
  | "server"
  | "rate-limit"
  | "generic";

export interface ErrorAlertProps {
  title?: string;
  message: string;
  type?: ErrorType;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

const ERROR_CONFIG: Record<
  ErrorType,
  {
    icon: LucideIcon;
    defaultTitle: string;
    badge: string;
  }
> = {
  validation: {
    icon: AlertCircle,
    defaultTitle: "Kiritilgan matnda kamchilik",
    badge: "Validatsiya",
  },
  network: {
    icon: WifiOff,
    defaultTitle: "Tarmoq bilan aloqa uzildi",
    badge: "Tarmoq xatosi",
  },
  server: {
    icon: ServerCrash,
    defaultTitle: "Serverda nosozlik yuz berdi",
    badge: "Server xatosi",
  },
  "rate-limit": {
    icon: AlertTriangle,
    defaultTitle: "So'rovlar chegarasi yetdi (Rate Limit)",
    badge: "Limit",
  },
  generic: {
    icon: AlertTriangle,
    defaultTitle: "Kutilmagan xatolik yuz berdi",
    badge: "Xatolik",
  },
};

export function ErrorAlert({
  title,
  message,
  type = "generic",
  onRetry,
  onDismiss,
  className,
}: ErrorAlertProps) {
  const config = ERROR_CONFIG[type] || ERROR_CONFIG.generic;
  const Icon = config.icon;
  const displayTitle = title || config.defaultTitle;

  return (
    <div
      role="alert"
      className={cn(
        "relative flex flex-col gap-3 rounded-xl border border-rose-200/90 bg-rose-50/70 p-4 shadow-subtle sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-rose-100 text-rose-600">
          <Icon className="h-4 w-4" />
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h4 className="text-xs font-semibold text-rose-950">
              {displayTitle}
            </h4>
            <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-medium text-rose-700">
              {config.badge}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-rose-800/90">{message}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 self-end sm:self-center">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-medium text-rose-800 shadow-subtle hover:bg-rose-50/80 active:scale-[0.98] transition-[color,background-color,border-color,transform] duration-150 ease-out"
          >
            <RotateCw className="h-3 w-3" />
            <span>Qayta urinish</span>
          </button>
        )}

        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Yopish"
            className="rounded p-1 text-rose-500 hover:bg-rose-100 hover:text-rose-800 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

export default ErrorAlert;
