export function LoadingState({ lines = 2 }: { lines?: number }) {
  return (
    <div className="loading-state" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="skeleton"
          style={{ marginTop: index === 0 ? 0 : 12, width: index === 1 ? "70%" : "100%" }}
        />
      ))}
    </div>
  );
}
