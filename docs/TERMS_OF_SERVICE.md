# Terms of Service and Acceptable Use for AI Moderator

**Effective Date:** July 10, 2026  
**Last Updated:** July 10, 2026

These terms govern use of AI Moderator, including the local API, moderation
pipeline, rules, policies, trained model artifacts, scripts, and documentation.

## 1. Service Description

AI Moderator provides local moderation analysis for platform messages. It may
return labels, confidence values, risk scores, explanations, and recommended
actions.

It is designed to be integrated with platform adapters such as OmniBot, Discord
bots, Telegram bots, dashboards, and internal moderation tools.

## 2. Administrator Responsibilities

Operators and server administrators are responsible for:

- choosing which channels or communities are covered;
- configuring policies and thresholds;
- reviewing destructive action limits before production use;
- informing users when AI moderation is active;
- handling appeals, false positives, and false negatives;
- securing API keys, database credentials, model files, logs, and backups.

## 3. Acceptable Use

You may use AI Moderator, with proper commercial permission, to:

- moderate communities you own or administer;
- detect spam, scams, abuse, unsafe content, and policy violations;
- support human moderation review;
- run local inference and health checks;
- evaluate and improve moderation policies for the licensed deployment.

## 4. Prohibited Use

You may not use AI Moderator to:

- violate laws, platform rules, or privacy rights;
- harass, discriminate against, or target users unfairly;
- secretly surveil communities without a lawful basis;
- sell, redistribute, or host the software without a commercial license;
- publish private logs, datasets, or model artifacts outside the licensed scope;
- claim AI decisions are infallible or deny reasonable human review;
- bypass API keys, access controls, or deployment security.

## 5. AI Limitations

AI Moderator is an assistive system. It may be wrong. Operators must use human
judgment for severe penalties, appeals, edge cases, and policy changes.

## 6. External Integrations

The default design is local/self-hosted. If an operator connects third-party
model providers, storage, monitoring, or platform APIs, that operator is
responsible for complying with those third-party terms and updating user-facing
privacy notices.

## 7. License

This project is proprietary commercial software. Use is allowed only under the
rights granted in a separate written commercial license or contract.

See [LICENSE](../LICENSE) and [COMMERCIAL_LICENSE.md](../COMMERCIAL_LICENSE.md).

## 8. Availability And Warranty

The software is provided "as is". No guarantee is made for uninterrupted
operation, model accuracy, moderation correctness, compatibility, or data
recovery.

## 9. Changes

These terms may be updated when features, infrastructure, laws, or deployment
requirements change.
