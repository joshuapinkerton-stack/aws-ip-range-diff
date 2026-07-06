import json
from datetime import datetime, timezone

from apify import Actor
from crawlee.crawlers import Router

router = Router[dict]()


@router.handler('snapshot')
async def handle_snapshot(context) -> None:
    response = await context.get_current_page().response_async()
    raw = await response.json()
    crawled_at = datetime.now(timezone.utc).isoformat()

    prefixes = raw.get('prefixes', [])
    ipv6_prefixes = raw.get('ipv6_prefixes', [])
    services = sorted({p.get('service') for p in prefixes})

    for p in prefixes:
        p['_family'] = 'ipv4'
    for p in ipv6_prefixes:
        p['_family'] = 'ipv6'

    await context.add_requests([
        {
            'url': 'apify://internal/ranges',
            'method': 'POST',
            'payload': json.dumps({'prefixes': prefixes, 'ipv6_prefixes': ipv6_prefixes}).encode('utf-8'),
            'headers': {'content-type': 'application/json'},
            'userData': {'handler': 'ranges'},
        }
    ])

    try:
        await Actor.charge('snapshot', {
            'url': response.url,
            'crawledAt': crawled_at,
            'prefixCount': len(prefixes),
            'ipv6PrefixCount': len(ipv6_prefixes),
            'serviceCount': len(services),
            'services': services,
        })
    except RuntimeError:
        Actor.log.debug('Charge skipped: not in a billing session.')

    context.log.info(
        f'Collected snapshot: {len(prefixes)} IPv4, {len(ipv6_prefixes)} IPv6 prefixes'
    )


@router.handler('ranges')
async def handle_ranges(context) -> None:
    payload_raw = await context.get_current_page().content_async()
    try:
        payload = json.loads(payload_raw)
    except Exception:
        payload = {}

    prefixes = payload.get('prefixes', [])
    ipv6_prefixes = payload.get('ipv6_prefixes', [])

    kvs = await Actor.open_key_value_store()
    previous_data = await kvs.get_value('previous_ip_ranges') or {'prefixes': [], 'ipv6_prefixes': []}
    previous_index = {_key(p): p for p in previous_data.get('prefixes', [])}
    previous_v6_index = {_key(p): p for p in previous_data.get('ipv6_prefixes', [])}

    dataset = await Actor.open_dataset()
    emitted = 0

    for p in prefixes:
        item = {
            'family': 'ipv4',
            'ipPrefix': p.get('ip_prefix'),
            'region': p.get('region'),
            'service': p.get('service'),
            'networkBorderGroup': p.get('network_border_group'),
            'changeType': _diff(previous_index, _key(p), p),
            'detectedAt': datetime.now(timezone.utc).isoformat(),
        }
        await dataset.push_data(item)
        try:
            await Actor.charge('range_entry', item)
        except RuntimeError:
            pass
        emitted += 1

    for p in ipv6_prefixes:
        item = {
            'family': 'ipv6',
            'ipPrefix': p.get('ipv6_prefix'),
            'region': p.get('region'),
            'service': p.get('service'),
            'networkBorderGroup': p.get('network_border_group'),
            'changeType': _diff(previous_v6_index, _key(p), p),
            'detectedAt': datetime.now(timezone.utc).isoformat(),
        }
        await dataset.push_data(item)
        try:
            await Actor.charge('range_entry', item)
        except RuntimeError:
            pass
        emitted += 1

    # Persist current snapshot for next run
    await kvs.set_value('previous_ip_ranges', {
        'prefixes': prefixes,
        'ipv6_prefixes': ipv6_prefixes,
    })

    context.log.info(f'Diff complete: {emitted} range rows emitted')


def _key(p: dict) -> str:
    return f"{p.get('ip_prefix') or p.get('ipv6_prefix')}|{p.get('region')}|{p.get('service')}"


def _diff(previous_index: dict, key: str, current: dict) -> str:
    prev = previous_index.get(key)
    if prev is None:
        return 'added'
    # AWS format is stable; if present it's unchanged.
    # Future enhancement: compare boundary metadata when available.
    return 'unchanged'
