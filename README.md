# AWS IP Range Change Detector

Tracks the public AWS IP ranges feed (`ip-ranges.json`) between runs and emits added, removed, and unchanged ranges as structured records.

## Buyer personas

- **B2B**: network security teams, SOC analysts, cloud firewall automation engineers, AWS architects, compliance teams.
- **B2C**: homelab operators, AWS cost explorers, journalists tracking AWS footprint changes.

## Example input

```json
{
  "awsIpRangesUrl": "https://ip-ranges.amazonaws.com/ip-ranges.json",
  "previousSnapshotKey": "previous_ip_ranges"
}
```

## Output events

| Event | Shape |
|-------|-------|
| `snapshot` | Run metadata and service counts |
| `range_entry` | One row per IPv4/IPv6 prefix with `changeType` |

## Pricing

Pay-per-Event: `$0.03/range_entry` + `$0.06/snapshot`.

## Local testing

```bash
python -m aws_ip_range_diff
```
