# Issue 08 - Câmara legislative votes coverage

Phase: 05-expansion
Status: completed

## Goal

Expand the Câmara legislative slice beyond the initial single-vote sample so the product can answer approved-project and nominal-vote questions on more than one record.

## Scope

- Multiple approved Câmara propositions.
- Multiple nominal votes with yes / no / other breakdowns.
- Vote-member records for each approved vote.
- Stable provenance for proposition, vote, authors, members, raw records, evidence, facts, and claims.
- Public discovery path for the legislative vote slice.

## Dependencies

- Issue 02.
- Issue 04.
- Issue 05.
- Existing Câmara legislative sample in the expansion branch.

## Acceptance criteria

- The database contains more than one approved Câmara proposition with nominal vote breakdowns.
- The API can return each approved vote with source, dataset, raw records, evidence, and member-level votes.
- The public UI exposes the broader legislative coverage instead of a single demonstration record.

## Notes

- Keep the scope on Câmara first, because the official Câmara API is accessible and can be validated directly.
- Do not treat the existing single-vote sample as sufficient for the objective.
- The live slice now covers 15 approved votes, with 3 nominal votes that expose member-level records and 12 symbolic approvals that do not expose individual votes. The provenance chain and public discovery path stay intact for both kinds of records.
