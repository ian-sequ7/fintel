import type { AlgorithmSignal } from "../../data/types";

interface Props {
  signal: AlgorithmSignal;
}

export default function SignalCard({ signal }: Props) {
  const isLong = signal.signalType.includes("long");
  const signalColor = isLong ? "text-success" : "text-danger";
  const bgColor = isLong ? "bg-green-500/10" : "bg-red-500/10";

  return (
    <div className={`rounded-lg border border-border-subtle p-4 ${bgColor}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-text-primary">{signal.ticker}</span>
          <span className={`text-sm font-medium ${signalColor} uppercase`}>
            {signal.signalType.replace("_", " ")}
          </span>
        </div>
        <span className="text-sm text-text-secondary">
          {Math.round(signal.confidence * 100)}% confidence
        </span>
      </div>

      <p className="text-sm text-text-secondary mb-3">{signal.rationale}</p>

      <div className="flex gap-4 text-sm">
        {signal.suggestedEntry && (
          <div>
            <span className="text-text-muted">Entry: </span>
            <span className="text-text-primary">${signal.suggestedEntry.toFixed(2)}</span>
          </div>
        )}
        {signal.suggestedStop && (
          <div>
            <span className="text-text-muted">Stop: </span>
            <span className="text-danger">${signal.suggestedStop.toFixed(2)}</span>
          </div>
        )}
        {signal.suggestedTarget && (
          <div>
            <span className="text-text-muted">Target: </span>
            <span className="text-success">${signal.suggestedTarget.toFixed(2)}</span>
          </div>
        )}
      </div>

      <div className="mt-2 text-xs text-text-muted">
        {signal.algorithmName} • {new Date(signal.timestamp).toLocaleString()}
      </div>
    </div>
  );
}
