"""Predicate cardinality governs storage, ordinary recall, and ingestion gates."""
import pytest

from aletheia import Memory
from aletheia.core.errors import ValidationError


@pytest.fixture
def memory(tmp_path):
    with_memory = Memory.open(str(tmp_path / 'memory.db'))
    yield with_memory
    with_memory.close()


def remember(memory, value, **kwargs):
    return memory.remember(subject='user', predicate='likes', object=value,
                           memory_type='preference', **kwargs)


def test_set_members_coexist_in_ordinary_recall_but_single_values_conflict(memory):
    declaration = memory.set_predicate_semantics('likes', cardinality='multiple')
    assert declaration['semantics'] == 'set_membership'
    a, b = remember(memory, 'coffee'), remember(memory, 'tea')
    assert memory.read_claim(a.id).status == memory.read_claim(b.id).status == 'active'
    assert not memory.list_conflicts()
    assert {r.claim_id for r in memory.retrieve(subject='user', predicate='likes')} == {a.id, b.id}

    memory.set_predicate_semantics('home_city', cardinality='single')
    for city in ('Paris', 'London'):
        memory.remember(subject='user', predicate='home_city', object=city, memory_type='fact')
    assert len(memory.list_conflicts()) == 1
    assert memory.retrieve(subject='user', predicate='home_city') == []
    assert len(memory.retrieve(subject='user', predicate='home_city', include_disputed=True)) == 2


def test_default_single_and_namespace_isolation(memory):
    memory.set_predicate_semantics('likes', cardinality='multiple', namespace='other')
    assert memory.get_predicate_semantics('likes')['cardinality'] == 'single'
    a, b = remember(memory, 'coffee'), remember(memory, 'tea')
    assert memory.read_claim(a.id).status == memory.read_claim(b.id).status == 'disputed'


def test_duplicates_still_detected_for_sets(memory):
    memory.set_predicate_semantics('likes', cardinality='multiple')
    a, b = remember(memory, 'coffee'), remember(memory, 'COFFEE')
    families = memory.list_conflict_families()
    assert len(families) == 1
    assert families[0].conflict_type == 'duplicate_claim'
    assert memory.read_claim(a.id).status == memory.read_claim(b.id).status == 'active'


def test_persistence_case_insensitive_lookup_and_additive_migration(memory):
    path = memory.store.path
    memory.set_predicate_semantics('LIKES', cardinality='multiple')
    reopened = Memory.open(path)
    try:
        assert reopened.get_predicate_semantics('likes')['cardinality'] == 'multiple'
    finally:
        reopened.close()
    memory.store.connection.execute('DROP TABLE predicate_semantics')
    reopened = Memory.open(path)
    try:
        assert reopened.get_predicate_semantics('likes')['cardinality'] == 'single'
    finally:
        reopened.close()


@pytest.mark.parametrize('cardinality', ['many', '', None, []])
def test_invalid_cardinality(memory, cardinality):
    with pytest.raises(ValidationError):
        memory.set_predicate_semantics('likes', cardinality=cardinality)


def test_declaration_change_preserves_disputes(memory):
    a, b = remember(memory, 'coffee'), remember(memory, 'tea')
    memory.set_predicate_semantics('likes', cardinality='multiple')
    assert memory.read_claim(a.id).status == memory.read_claim(b.id).status == 'disputed'
    assert memory.list_conflicts()[0].status == 'unresolved'


@pytest.mark.parametrize('cardinality', ['single', 'multiple'])
def test_candidate_screening_and_promotion(memory, cardinality):
    ns = memory.namespace
    batch = memory.ingest(ns, source_type='conversation_transcript',
                          content='For progress updates, keep it concise.')
    run = memory.extract_candidates(ns, batch_id=batch.id)
    candidate = memory.list_candidates(ns, extraction_run_id=run.id)[0]
    memory.reject_candidate(candidate.id, reason='Discard exploratory extraction')
    memory.set_predicate_semantics(candidate.predicate, cardinality=cardinality)
    memory.remember(subject=candidate.subject, predicate=candidate.predicate,
                    object='long and detailed', memory_type='preference')
    run = memory.extract_candidates(ns, batch_id=batch.id)
    candidate = memory.list_candidates(ns, extraction_run_id=run.id)[0]
    assert candidate.contradiction_risk == (0.0 if cardinality == 'multiple' else 0.90)
    if cardinality == 'single':
        assert candidate.candidate_status == 'needs_conflict_resolution'
        with pytest.raises(ValidationError):
            memory.promote_candidate(candidate.id, reason='must remain blocked')
    else:
        memory.review_candidate(candidate.id, decision='validate', reason='direct statement')
        claim = memory.promote_candidate(candidate.id, reason='compatible set member')
        assert claim.status == 'active'
        assert not memory.list_conflicts()


def test_candidate_promotion_rechecks_changed_cardinality(memory):
    ns = memory.namespace
    memory.set_predicate_semantics('prefers_response_style', cardinality='multiple')
    memory.remember(subject='user', predicate='prefers_response_style',
                    object='long and detailed', memory_type='preference')
    batch = memory.ingest(ns, source_type='conversation_transcript',
                          content='For progress updates, keep it concise.')
    run = memory.extract_candidates(ns, batch_id=batch.id)
    candidate = memory.list_candidates(ns, extraction_run_id=run.id)[0]
    assert candidate.contradiction_risk == 0
    memory.review_candidate(candidate.id, decision='validate', reason='direct statement')
    memory.set_predicate_semantics(candidate.predicate, cardinality='single')
    with pytest.raises(ValidationError, match='contradiction'):
        memory.promote_candidate(candidate.id, reason='stale screening must not bypass gate')


def test_old_candidate_risk_is_not_silently_cleared(memory):
    ns = memory.namespace
    memory.remember(subject='user', predicate='prefers_response_style',
                    object='long and detailed', memory_type='preference')
    batch = memory.ingest(ns, source_type='conversation_transcript',
                          content='For progress updates, keep it concise.')
    run = memory.extract_candidates(ns, batch_id=batch.id)
    candidate = memory.list_candidates(ns, extraction_run_id=run.id)[0]
    assert candidate.contradiction_risk == .90
    memory.set_predicate_semantics(candidate.predicate, cardinality='multiple')
    with pytest.raises(ValidationError, match='contradiction'):
        memory.promote_candidate(candidate.id, reason='stored risk still requires review')


@pytest.mark.parametrize('cardinality', ['single', 'multiple'])
def test_inference_gate_uses_predicate_semantics(memory, cardinality):
    from types import SimpleNamespace

    memory.set_predicate_semantics('likes', cardinality=cardinality)
    source = remember(memory, 'coffee')
    inference = SimpleNamespace(
        namespace=memory.namespace, subject='user', predicate='likes', object='tea',
        source_claim_ids=[source.id], source_evidence_ids=source.evidence_ids,
        status='validated', inference_strength='entailed', suggested_truth_confidence=.95,
    )
    failures = memory._inference_promotion_failures(inference, 'claim', 'active')
    assert ('inference conflicts with an active claim' in failures) == (cardinality == 'single')


def test_semantics_changes_invalidate_review_snapshot(memory):
    def epoch():
        return memory.store.connection.execute('SELECT epoch FROM review_state WHERE id=1').fetchone()[0]

    before = epoch()
    memory.set_predicate_semantics('likes', cardinality='multiple')
    assert epoch() > before
    before = epoch()
    memory.set_predicate_semantics('likes', cardinality='single')
    assert epoch() > before
