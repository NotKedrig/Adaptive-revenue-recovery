# Payment Recovery Strategy Guide

## Overview

This document provides detailed guidance on recovery strategy selection, timing optimization, and multi-channel communication for the AI Revenue Recovery system. It complements the failure codes reference by focusing on the "how" and "when" of recovery actions.

---

## Recovery Timing Windows

### Critical First Hour
For transient failures (bank_timeout, network_error), the first hour after failure is the highest-value window:
- Customer intent is still fresh
- The underlying issue may have already resolved
- Retry success rates are highest in this window

**Recommendation:** For purely technical failures, attempt the first retry within 15-30 minutes.

### The 24-Hour Sweet Spot
For customer-related failures (insufficient_funds, authentication_failed), waiting 24 hours is typically optimal:
- Salary deposits often occur on specific dates (1st, 15th, last day of month)
- Customer may have resolved the issue independently
- Avoids appearing aggressive

**Recommendation:** For insufficient_funds, check if the failure date is close to common salary dates and time the retry accordingly.

### The Decay Curve
Recovery probability decays exponentially:
- Day 0-1: 60-80% recovery potential
- Day 2-3: 40-60% recovery potential
- Day 4-7: 20-40% recovery potential
- Day 7+: Below 15% recovery potential

**Recommendation:** Prioritize speed. Every hour of delay reduces recovery probability by approximately 1-2%.

---

## Multi-Channel Communication Strategy

### Email Recovery
**Best for:** Expired card updates, subscription renewal reminders, detailed payment breakdowns
**Timing:** Send during business hours (9 AM - 6 PM customer local time)
**Content:** Include payment details, reason for failure, clear CTA button, support contact
**Response rate:** 15-25% open rate, 5-10% action rate

### SMS Recovery
**Best for:** Time-sensitive payment reminders, OTP re-authentication prompts
**Timing:** Send during waking hours (8 AM - 9 PM customer local time)
**Content:** Keep under 160 characters, include payment link, merchant name
**Response rate:** 40-60% read rate, 10-15% action rate
**Constraint:** Limit to 2 SMS per recovery case to avoid spam complaints

### Payment Link Generation
**Best for:** Any scenario requiring customer re-authentication or updated payment details
**Expiry:** Links should expire within 48-72 hours
**Security:** One-time use, customer-specific, amount-locked
**Include:** Pre-filled amount, merchant details, and failure context

---

## Amount-Based Strategy Selection

### Micro-Transactions (< ₹500)
- **Strategy:** Single retry + single notification
- **Rationale:** Cost of recovery efforts may exceed transaction value
- **Max attempts:** 2

### Standard Transactions (₹500 - ₹10,000)
- **Strategy:** Full recovery sequence (retry → notify → escalate)
- **Rationale:** Worthwhile to recover but not high-priority
- **Max attempts:** 5

### High-Value Transactions (₹10,000 - ₹50,000)
- **Strategy:** Prioritized recovery with personalized outreach
- **Rationale:** Significant revenue impact justifies additional effort
- **Max attempts:** 7

### Premium Transactions (> ₹50,000)
- **Strategy:** Immediate escalation to dedicated recovery team
- **Rationale:** High-value failures warrant personalized, white-glove treatment
- **Max attempts:** 10
- **Additional:** Consider phone call outreach

---

## Subscription vs One-Time Payment Recovery

### Subscription Payments
Subscription failures have additional context that improves recovery:
- **Customer lifetime value** justifies more aggressive recovery
- **Payment history** provides data on when the customer typically has funds
- **Relationship context** allows for grace periods without service disruption
- **Dunning sequences** can be multi-step over several days

**Key metric:** Subscription recovery directly reduces churn. A 5% improvement in recovery rate can translate to 15-20% improvement in annual retention.

### One-Time Payments
One-time payments have different dynamics:
- **Customer intent decays rapidly** — especially for impulse purchases
- **No historical payment data** for timing optimization
- **Lower tolerance for multiple notifications** — customer may feel harassed
- **Higher fraud risk** — one-time payments from new customers warrant extra scrutiny

---

## Risk Indicators to Monitor

### Fraud Signals
- Multiple failed payments from different cards on the same account
- Rapid succession of small test transactions
- Geographic mismatch between customer profile and transaction origin
- Use of known BIN ranges associated with fraud
- Velocity of transactions exceeding normal patterns

### Customer Distress Signals
- Repeated insufficient funds failures across multiple billing cycles
- Customer contacting support about financial hardship
- Unsubscribe or opt-out requests during recovery sequence

### System Health Signals
- Spike in timeout errors from a specific issuer bank
- Elevated failure rates across multiple merchants
- Bank maintenance windows causing clustered failures

---

## Compliance Requirements

### RBI Guidelines (India)
- Auto-debit mandates require explicit customer consent
- Maximum retry limits apply to recurring mandates
- Customer must be notified before and after each debit attempt
- Opt-out must be honored immediately

### PCI DSS Considerations
- Never log or store full card numbers in recovery communications
- Payment links must be transmitted over encrypted channels
- Recovery agents must not have access to raw card data

### Anti-Spam Regulations
- Honor DND (Do Not Disturb) registry preferences
- Maximum 1 promotional SMS per day
- Clear unsubscribe mechanism in all email communications
- Maintain audit trail of all customer communications
