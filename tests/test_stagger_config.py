import pytest
from app.workflows.staggered_enrichment import StaggeredEnrichmentWorkflow

STAGGER_CONFIG = {
    'wave_policies': {
        'teile_com': {
            'waves': 3,
            'wave_delays_seconds': [0, 300, 900],
            'jitter_seconds': 30,
            'escalation_threshold': 0.4,
            'quorum_required': 2,
            'fetcher_priority': ['crawl4ai', 'scrapling', 'camoufox'],
        },
    },
    'default_policy': {
        'waves': 2,
        'wave_delays_seconds': [0, 600],
        'jitter_seconds': 60,
        'escalation_threshold': 0.5,
        'quorum_required': 1,
        'fetcher_priority': ['crawl4ai'],
    },
}


class TestStaggeredEnrichmentWorkflow:
    def setup_method(self):
        self.workflow = StaggeredEnrichmentWorkflow(STAGGER_CONFIG, "http://localhost:18000/v1")

    def test_get_policy_returns_domain_specific(self):
        policy = self.workflow._get_policy('teile.com')
        assert policy['waves'] == 3
        assert policy['quorum_required'] == 2

    def test_get_policy_falls_back_to_default(self):
        policy = self.workflow._get_policy('unknown-domain.com')
        assert policy['waves'] == 2

    def test_compute_delay_includes_jitter(self):
        policy = STAGGER_CONFIG['wave_policies']['teile_com']
        delay = self.workflow._compute_delay(1, policy)
        assert 300 <= delay <= 330
