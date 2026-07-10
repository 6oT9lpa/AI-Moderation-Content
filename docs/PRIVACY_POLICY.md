# Privacy Policy for AI Moderator

**Effective Date:** July 10, 2026  
**Last Updated:** July 10, 2026

This policy explains what data AI Moderator processes when it is used as a
local/self-hosted moderation API.

## 1. Operator

Project operator: **6oT9lpa / AI Moderator project team**.

The organization or server administrator deploying AI Moderator is responsible
for choosing which platform messages are sent to the API and for informing users
when AI moderation is active.

## 2. Data Processed

AI Moderator may process:

- platform name, guild/server/chat ID, channel ID, message ID, and user ID;
- message text and normalized text;
- timestamps and request correlation IDs;
- user context such as account age, member age, roles, and recent behavior when
  provided by the calling platform;
- policy context such as guild, channel, role, and user scope;
- rule matches, labels, confidence values, risk scores, reason codes, and
  decision actions;
- model metadata, model version, latency, and error details;
- technical logs required for debugging and reliability.

If media/OCR features are enabled in a deployment, the service may also process
attachment metadata, hashes, OCR text, and media analysis signals.

## 3. Purpose

Data is used to:

- classify moderation risk;
- apply preprocessing rules and model inference;
- resolve moderation policies;
- return decisions to the calling platform adapter;
- support audit, debugging, evaluation, regression checks, and model
  improvement;
- monitor service health and reliability.

## 4. Local Processing

The intended production deployment is local/self-hosted. By default, AI
Moderator does not need to send message content to a commercial third-party AI
API. Model inference can run locally on CPU or CUDA GPU.

If a deployment enables external services later, the operator must document that
change and update this policy for affected users.

## 5. Retention

Retention depends on deployment configuration. Technical logs, audit records,
dataset exports, and policy records should be retained only as long as needed
for moderation, security, debugging, training, or legal requirements.

Release archives and backups should exclude `.env`, logs, virtual environments,
runtime data, and model directories unless an operator intentionally backs them
up under a protected process.

## 6. Access And Deletion

Requests for access, correction, or deletion should include:

- platform user ID;
- server/guild/chat ID;
- approximate message time or message ID if available;
- requested action: export, correct, delete, or disable.

The operator may need to verify that the requester is the relevant user or an
authorized administrator.

## 7. Security

Recommended safeguards:

- run the API on localhost or a private network;
- require an internal API key;
- keep secrets in `.env`;
- restrict database access;
- restrict model and dataset directories;
- log security-relevant failures;
- protect backups and exports;
- keep NVIDIA/CUDA and Python dependencies updated.

## 8. Limitations

AI Moderator may produce false positives and false negatives. It should assist
moderation teams, not replace human judgment or appeals.

## 9. Changes

This policy may be updated when features, infrastructure, laws, or deployment
requirements change.
