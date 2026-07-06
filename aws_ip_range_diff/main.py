import json
from collections import defaultdict
from datetime import datetime, timezone

from apify import Actor
from crawlee.crawlers import CheerioCrawler
from crawlee import router

from .routes import router as diff_router


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        aws_url = actor_input.get(
            'awsIpRangesUrl',
            'https://ip-ranges.amazonaws.com/ip-ranges.json',
        )

        previous_snapshot_key = actor_input.get('previousSnapshotKey', 'previous_ip_ranges')

        # Load previous snapshot from key-value store
        kvs = await Actor.open_key_value_store()
        previous_raw = await kvs.get_value(previous_snapshot_key) or {'prefixes': [], 'ipv6_prefixes': []}
        previous_index = {_range_key(r): r for r in previous_raw.get('prefixes', [])}
        previous_v6_index = {_range_key(r): r for r in previous_raw.get('ipv6_prefixes', [])}

        # Crawl current snapshot
        initial_requests = [{'url': aws_url, 'userData': {'handler': 'snapshot'}}]
        crawler = CheerioCrawler(
            max_requests_per_crawl=3,
            max_request_retries=4,
            request_handler=diff_router,
        )

        results = {'prefixes': [], 'ipv6_prefixes': []}

        # Capture emitted records via Actor.open_dataset side-effect in routes.
        # We post-process after the crawl finishes.
        await crawler.run(initial_requests)

        dataset = await Actor.open_dataset()
        await dataset.push_data({
            'type': 'diff_run_meta',
            'crawledAt': datetime.now(timezone.utc).isoformat(),
            'awsUrl': aws_url,
        })

        Actor.log.info('AWS IP range diff actor completed.')


def _range_key(r: dict) -> str:
    return f"{r.get('ip_prefix') or r.get('ipv6_prefix')}|{r.get('region')}|{r.get('service')}"
