# Payment Failure Codes & Recovery Reference

## Overview

This document catalogs common payment failure codes, their causes, recoverability assessment, and recommended recovery strategies. It serves as the primary reference for the AI Diagnosis Agent when classifying payment failures and determining next steps.

---

## Failure Code: insufficient_funds

**Category:** Transient — Customer Account  
**Severity:** Medium  
**Recoverability:** High (with delay)

**Description:** The customer's bank account or card did not have sufficient balance to complete the transaction at the time of the attempt.

**Common Causes:**
- Salary or income not yet deposited
- Customer spent funds after initiating a subscription or standing instruction
- Timing mismatch between billing cycle and pay cycle

**Recovery Strategy:**
- **Wait & Retry:** Delay retry by 24–72 hours. The customer may have funds after their next deposit.
- **Notify:** Send a polite payment reminder via email or SMS informing the customer that their payment could not be processed due to insufficient funds.
- **Do NOT:** Immediately retry within minutes — this wastes attempts and may trigger fraud detection at the issuer.

**Recoverability Notes:**
Historically, insufficient funds failures have a 40–60% recovery rate when retried after a 2–3 day delay. Success rate drops significantly after 7 days.

---

## Failure Code: expired_card

**Category:** Permanent — Card Lifecycle  
**Severity:** High  
**Recoverability:** Low (retry alone will not resolve)

**Description:** The card used for the transaction has passed its expiration date. The issuing bank has rejected the transaction because the card credentials are no longer valid.

**Common Causes:**
- Card was not renewed by the customer
- Customer received a new card but did not update their payment method on file
- Auto-renewal of card number by issuer (requires updated details)

**Recovery Strategy:**
- **Notify Customer:** Send a targeted email or SMS asking the customer to update their card details.
- **Payment Link:** Include a secure payment link so the customer can re-authorize with updated card information.
- **Do NOT Retry:** Retrying with the same expired card will always fail. This is a permanent failure until the customer provides new card details.

**Recoverability Notes:**
Expired card failures require customer action. Recovery rates are 20–35% when a clear notification with a payment link is sent within 48 hours. After 7 days, recovery drops below 10%.

---

## Failure Code: invalid_card

**Category:** Permanent — Card Validation  
**Severity:** Critical  
**Recoverability:** Very Low

**Description:** The card number, CVV, or other credentials provided are invalid. The issuer cannot locate an account matching the provided card details.

**Common Causes:**
- Incorrect card number entered by the customer
- Stolen or cloned card number that does not match issuer records
- Test card used in production
- Card was closed or cancelled by the issuer

**Recovery Strategy:**
- **Do NOT Retry:** Invalid card will never succeed with the same details.
- **Notify:** Inform the customer that their card could not be validated, and request updated payment details.
- **Fraud Check:** If the card number pattern suggests fraud, flag for compliance review.

**Recoverability Notes:**
If the root cause is a typo, customer notification with a corrected payment link can recover 10–20% of cases. If the card is truly invalid or cancelled, recovery is effectively zero without a new payment method.

---

## Failure Code: bank_timeout

**Category:** Transient — Network/Infrastructure  
**Severity:** Low  
**Recoverability:** Very High

**Description:** The transaction timed out waiting for a response from the issuing bank's authorization system. No funds were debited.

**Common Causes:**
- Bank server overload (common during peak hours, month-end salary processing, festive sales)
- Network connectivity issues between the payment gateway and the bank
- Scheduled bank maintenance windows

**Recovery Strategy:**
- **Immediate Retry:** Safe to retry within 15–60 minutes.
- **Time-of-Day Awareness:** If timeout occurred during peak hours (10 AM–2 PM IST, month-end), retry during off-peak hours.
- **Multiple Retries:** Up to 3 retries within 24 hours are appropriate for timeout failures.
- **Escalate:** If 3 retries all time out, switch to customer notification.

**Recoverability Notes:**
Bank timeout failures have a 70–85% recovery rate on immediate retry. If the bank's systems were genuinely down, retrying after 1–4 hours is usually sufficient.

---

## Failure Code: authentication_failed

**Category:** Transient — Customer Authentication  
**Severity:** Medium  
**Recoverability:** Medium (requires customer re-authentication)

**Description:** The 3D Secure (3DS), OTP, or biometric authentication step failed. The customer may have entered an incorrect OTP, let the authentication page time out, or their bank's authentication system encountered an error.

**Common Causes:**
- Customer entered the wrong OTP
- OTP expired before the customer entered it
- Customer's phone did not receive the OTP due to network issues
- Bank's 3DS authentication server was temporarily unavailable

**Recovery Strategy:**
- **Send Payment Link:** Generate a new payment link so the customer can re-attempt the authentication step.
- **Notify:** Inform the customer that their payment requires re-authentication.
- **Do NOT Retry Silently:** Cannot bypass the authentication requirement — customer action is needed.
- **Time Sensitivity:** Payment links should be sent promptly; customer intent decays rapidly (within 1 hour for impulse purchases, within 24 hours for subscriptions).

**Recoverability Notes:**
If the cause was a genuine OTP failure, recovery via payment link is 30–50%. If the bank's 3DS system was down, automatic retry after 2–4 hours may succeed without customer action.

---

## Failure Code: issuer_decline

**Category:** Transient or Permanent — Issuer Decision  
**Severity:** Medium–High  
**Recoverability:** Low–Medium

**Description:** The issuing bank has explicitly declined the transaction. The decline reason is often generic ("Do Not Honor"), making root cause analysis difficult.

**Common Causes:**
- Velocity limits exceeded (too many transactions in a short period)
- Risk scoring triggered by unusual purchase pattern
- Card flagged by issuer for suspicious activity
- International transaction blocked by domestic-only card
- Customer's credit limit reached

**Recovery Strategy:**
- **Categorize the Sub-Code:** If a more specific decline sub-code is available, use it to refine the diagnosis.
- **Delayed Retry:** Wait 24–48 hours before retrying. Some issuer risk flags are time-limited.
- **Alternative Payment Method:** If retry fails, ask the customer to try a different card or payment method.
- **Do NOT aggressively retry:** Multiple rapid retries on a declined card may cause the issuer to permanently block the card-merchant pair.

**Recoverability Notes:**
Generic "Do Not Honor" declines have a 15–30% recovery rate on delayed retry. If the decline is due to credit limit or velocity, recovery depends on customer action.

---

## Failure Code: recurring_payment_failure

**Category:** Mixed — Subscription/Mandate  
**Severity:** High  
**Recoverability:** Medium

**Description:** A scheduled recurring payment (subscription, EMI, SIP) failed to process. This may be due to any of the above underlying causes, but the context of a recurring relationship adds additional recovery strategies.

**Common Causes:**
- Insufficient funds on the scheduled debit date
- Card expired since the subscription was set up
- Customer revoked the recurring mandate at their bank
- Standing instruction limit exceeded

**Recovery Strategy:**
- **Classify the Underlying Cause:** Determine which root failure code applies (insufficient_funds, expired_card, etc.) and apply the appropriate base strategy.
- **Grace Period:** Apply a 3–7 day grace period before marking the subscription as churned.
- **Dunning Sequence:** Initiate a multi-step notification sequence:
  1. Day 0: Email notification with payment link
  2. Day 2: SMS reminder
  3. Day 5: Final notice email
- **Re-mandate:** If the mandate was revoked, the customer must re-authorize. Send a re-authorization link.

**Recoverability Notes:**
Recurring payment recovery is highly time-sensitive. 50–70% of recoveries happen within the first 3 days. After 7 days, the recovery rate drops to 10–20% and the customer is likely to churn.

---

## Failure Code: network_error

**Category:** Transient — Network Infrastructure  
**Severity:** Low  
**Recoverability:** Very High

**Description:** A network-level error occurred between the payment gateway and the banking network. No financial transaction was initiated.

**Common Causes:**
- DNS resolution failure
- TCP connection timeout
- SSL/TLS handshake failure
- Load balancer health check failure
- CDN or proxy server error

**Recovery Strategy:**
- **Immediate Retry:** Safe to retry immediately or within 5–15 minutes.
- **No Customer Action Required:** This is a purely technical failure; the customer does not need to be notified.
- **Monitor:** If network errors spike across multiple transactions, escalate to operations team.

**Recoverability Notes:**
Network errors have a 90–95% recovery rate on immediate retry. If the error persists after 3 retries, it indicates a systemic infrastructure issue.

---

## General Recovery Rules

### Maximum Retry Limits
- **Transient failures (timeout, network):** Up to 5 retries within 48 hours
- **Customer-action-required failures (expired_card, authentication):** 0 retries; notification only
- **Ambiguous declines (issuer_decline):** Up to 2 retries with 24-hour delays
- **Permanent failures (invalid_card):** 0 retries; notification only

### Notification Best Practices
- Always include the merchant name and transaction amount
- Provide a clear call-to-action (payment link, update card link)
- Respect opt-out preferences
- Limit to 3 notifications per recovery case
- Space notifications at least 24 hours apart

### Escalation Triggers
- 3 or more failed retries → Escalate to notification-based recovery
- Customer unresponsive after 3 notifications → Escalate to human review
- Fraud indicators detected → Immediately escalate to compliance team
- Transaction amount exceeds policy threshold → Escalate to senior review

### Non-Recoverable Cases
The following should NOT be retried and should be closed immediately:
- Card reported as stolen or lost
- Customer explicitly requested cancellation
- Merchant account suspended or closed
- Transaction flagged as fraudulent by the issuer
- Regulatory or sanctions block
