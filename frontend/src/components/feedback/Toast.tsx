import { useEffect } from "react";

export function Toast({
  title,
  body,
  onDismiss,
}: {
  title: string;
  body?: string;
  onDismiss: () => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, 3200);
    return () => window.clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className="toast" role="status">
      <strong>{title}</strong>
      {body}
    </div>
  );
}
