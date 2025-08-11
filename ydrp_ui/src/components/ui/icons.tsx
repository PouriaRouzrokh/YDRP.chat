import { cn } from "@/lib/utils";
import {
  Loader2,
  SendIcon,
  PlusIcon,
  TrashIcon,
  SettingsIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
} from "lucide-react";

export function IconSpinner({
  className,
  ...props
}: React.ComponentProps<"svg">) {
  return (
    <Loader2 className={cn("h-4 w-4 animate-spin", className)} {...props} />
  );
}

export function IconSend({ className, ...props }: React.ComponentProps<"svg">) {
  return <SendIcon className={cn("h-4 w-4", className)} {...props} />;
}

export function IconPlus({ className, ...props }: React.ComponentProps<"svg">) {
  return <PlusIcon className={cn("h-4 w-4", className)} {...props} />;
}

export function IconTrash({
  className,
  ...props
}: React.ComponentProps<"svg">) {
  return <TrashIcon className={cn("h-4 w-4", className)} {...props} />;
}

export function IconSettings({
  className,
  ...props
}: React.ComponentProps<"svg">) {
  return <SettingsIcon className={cn("h-4 w-4", className)} {...props} />;
}

export function IconArrowLeft({
  className,
  ...props
}: React.ComponentProps<"svg">) {
  return <ArrowLeftIcon className={cn("h-4 w-4", className)} {...props} />;
}

export function IconArrowRight({
  className,
  ...props
}: React.ComponentProps<"svg">) {
  return <ArrowRightIcon className={cn("h-4 w-4", className)} {...props} />;
}
