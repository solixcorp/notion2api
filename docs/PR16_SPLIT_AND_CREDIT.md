# PR #16 Split and Contributor Attribution Plan

> Maintenance goal: incorporate the work of Sanity-Cloud / @insane66613 **primarily through their own commits / PR collaboration**, not a "copy everything and add a one-line thank-you".

## Principles

1. **Split into small PRs**: one topic at a time — reviewable, testable, revertable.
2. **Preserve author**: use `cherry-pick` to keep the original author (`Math Shamenson` / `insane66613`); do not rewrite the contributor's diff as a maintainer-only commit.
3. **Use GitHub Merge**: each small PR goes through the Merge button, leaving a Merged record and contribution stats.
4. **Maintainer only follows up on security/conflict fixes**: follow-up commits clearly state `fix after contrib:`, add `Co-authored-by` where appropriate.
5. **Invite as Collaborator**: Settings → Collaborators → invite `@insane66613` (repo setting, requires owner action).

## Split Order (aligned with original #17–#22)

| No. | Branch | Topic | Original PR | Risk |
|----:|--------|-------|-------------|------|
| 01 | `contrib/pr16-01-maintenance` | migration performance + minor cleanup | #17 | Low |
| 02 | `contrib/pr16-02-stream-hardening` | stream safe parser | #18 | Medium (affects thinking) |
| 03 | `contrib/pr16-03-model-registry` | model table additions | #19 | Medium (conflicts with main) |
| 04 | `contrib/pr16-04-attachments-core` | attachment core package (**tighten defaults**) | #20 | High (security) |
| 05 | `contrib/pr16-05-chat-history-ro` | history read-only/sync | #21 subset | High |
| 06 | `contrib/pr16-06-chat-history-write` | delete/cleanup destructive APIs | #21 remainder | Very high (requires API_KEY) |
| 07 | `contrib/pr16-07-frontend-history` | frontend history UI | #22 | Medium |
| 08 | Optional | MCP | within umbrella | High (last) |

**Do not**: directly merge the #16 umbrella PR; paste the contributor's code wholesale as a maintainer commit.

## PR Title Template

```text
[contrib #16/@insane66613] <topic>

Landed from Sanity-Cloud split (originally PR #N).
Author commits preserved via cherry-pick.
```

## #16 Itself

Close or keep as an index issue, with a comment linking to this split plan and the subsequent small PRs.
