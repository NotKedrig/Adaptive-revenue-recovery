import React from 'react';

export interface QueueItemProps {
  case_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  failure_type: string;
  status: string;
  latest_action?: string;
  latest_outcome?: string;
  onClick: (case_id: string) => void;
}

export const QueueItem: React.FC<QueueItemProps> = ({
  case_id,
  payment_id,
  amount,
  currency,
  failure_type,
  status,
  latest_action,
  latest_outcome,
  onClick
}) => {
  // Format currency
  const formattedAmount = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount);

  // Status styling
  const isRecovered = status === 'recovered';
  const isFailed = status === 'failed' || status === 'escalated';
  const isPending = !isRecovered && !isFailed;

  const statusClass = isRecovered 
    ? 'status-success' 
    : isFailed 
    ? 'status-error' 
    : 'status-pending';

  return (
    <div className="queue-item" onClick={() => onClick(case_id)}>
      <div className="queue-item-header">
        <span className="queue-item-id">{payment_id}</span>
        <span className="queue-item-amount">{formattedAmount}</span>
      </div>
      <div className="queue-item-body">
        <span className="queue-item-failure">Failure: {failure_type}</span>
        <span className={`queue-item-status ${statusClass}`}>{status.toUpperCase()}</span>
      </div>
      <div className="queue-item-footer">
        <span className="queue-item-action">
          {latest_action && latest_outcome ? `${latest_action} → ${latest_outcome}` : 'Processing...'}
        </span>
      </div>
    </div>
  );
};
