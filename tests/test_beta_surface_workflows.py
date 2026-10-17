"""Behavioral follow-ups selected from measured public-method coverage gaps."""
from contextlib import closing

import pytest

from aletheia import Memory
from aletheia.core.errors import NotFoundError


@pytest.fixture
def memory(tmp_path):
    with closing(Memory.open(str(tmp_path / 'surface.db'), namespace='surface/main')) as m:
        yield m


def test_contract_registration_is_discoverable_and_migration_is_idempotent(memory):
    before = memory.health()['schema_version']
    contract = memory.register_public_contract(contract_type='python_api', name='Synthetic surface contract',
        version='evaluation-v1', stability='experimental', metadata={'fixture': True})
    assert memory.get_public_contract(contract.id) == memory.get_public_contract(contract.name) == contract
    assert contract in memory.list_public_contracts(contract_type='python_api')
    memory.migrate()
    assert memory.health()['schema_version'] == before
    assert memory.get_public_contract(contract.id) == contract
    assert memory.list_api_contract_versions()
    assert isinstance(memory.list_deprecations(), list)
    matrix = memory.list_compatibility_matrix()
    assert matrix
    entry = matrix[0]
    assert memory.compatibility_status(component_type=entry.component_type,
        component_name=entry.component_name, component_version=entry.component_version)['status'] == entry.status
    assert memory.compatibility_status(component_type='missing', component_name='missing', component_version='missing')['status'] == 'unknown'


def test_conformance_receipts_expose_actual_case_outcomes(memory):
    suite = memory.get_conformance_suite('kernel')
    cases = memory.list_conformance_cases(suite.id)
    run = memory.run_conformance(suite='kernel')
    assert run.status == 'passed'
    assert memory.list_conformance_runs()[0].id == run.id
    results = memory.list_conformance_results(run.id)
    assert len(results) == len(cases)
    assert all(row.status == 'passed' for row in results)
    assert not memory.list_claims(namespace=memory.namespace)


def test_docs_doctor_gate_and_backup_keep_inspectable_receipts(memory, tmp_path):
    example = memory.scaffold_adapter(adapter_type='python-sdk', name='Synthetic surface adapter', output_path=str(tmp_path / 'adapter'))
    build = memory.build_docs(output_dir=str(tmp_path / 'docs'), validate_examples=False)
    assert memory.list_documentation_builds()[0].id == build.id
    assert memory.docs_status()['latest']['id'] == build.id
    assert (tmp_path / 'docs' / 'openapi.generated.json').is_file()
    assert any(row.id == example['id'] for row in memory.list_examples())
    doctor = memory.doctor_run()
    assert memory.get_doctor_run(doctor.id) == doctor
    assert memory.list_doctor_runs()[0].id == doctor.id
    gate = memory.v1_gate_run()
    assert gate.status == 'failed'  # External qualification is deliberately absent.
    assert memory.get_v1_gate_run(gate.id) == gate
    assert memory.list_v1_gate_runs()[0].id == gate.id
    backup = memory.create_backup(output_path=str(tmp_path / 'backup.alet'), namespace=memory.namespace, passphrase='synthetic-backup-fixture')
    assert memory.get_backup(backup.id).checksums == backup.checksums
    integrity = memory.integrity_check(namespace=memory.namespace)
    assert memory.list_integrity_runs()[0].id == integrity.id
    assert isinstance(memory.list_benchmarks(), list)


def test_workspace_removal_and_agent_group_state_survive_reopen(memory):
    identity = memory.create_federation_identity(display_name='Synthetic surface', protected=False)
    assert memory.get_federation_identity(identity.id) == identity
    workspace = memory.create_workspace(namespace=memory.namespace, name='Synthetic workspace')
    assert memory.get_workspace(workspace.name) == workspace
    member = memory.add_workspace_member(workspace.id, member_type='agent', member_id='agent-fixture', role='reader')
    assert memory.get_workspace_member(workspace.id, 'agent', 'agent-fixture') == member
    assert member in memory.list_workspace_members(workspace.id)
    memory.remove_workspace_member(workspace.id, 'agent-fixture')
    assert memory.get_workspace_member(workspace.id, 'agent', 'agent-fixture').status == 'removed'
    group = memory.create_agent_group(namespace=memory.namespace, name='Synthetic group', default_capabilities=['memory:read'])
    agent = memory.add_agent_group_member(group.id, agent_id='agent-fixture')
    assert memory.get_agent_group(group.name) == group
    assert memory.get_agent_group_member(group.id, 'agent-fixture') == agent
    assert agent in memory.list_agent_group_members(group.id)
    assert memory.agent_group_allows(group.id, 'memory:read')
    assert not memory.agent_group_allows(group.id, 'memory:admin')
    assert memory.list_federation_audit_events()
    assert memory.propagate_revocations()['status'] == 'completed'
    with closing(Memory.open(memory.store.path, namespace=memory.namespace)) as reopened:
        assert reopened.get_workspace_member(workspace.id, 'agent', 'agent-fixture').status == 'removed'
        assert reopened.get_agent_group_member(group.id, 'agent-fixture') == agent


def test_review_dismissal_and_notification_snooze_are_durable(memory):
    claim = memory.remember(memory_type='fact', subject='fixture', predicate='records', object='canary')
    task = memory.create_review_task(memory.namespace, task_type='candidate_review', title='Synthetic review',
        description='Explicit operator dismissal', target_id=claim.id, target_type='claim')
    assert memory.dismiss_review_task(task.id, reason='Synthetic operator decision').status == 'dismissed'
    assert memory.list_review_task_events(task.id)[-1].event_type == 'dismissed'
    notification = memory.create_notification(memory.namespace, notification_type='review_required', title='Synthetic', message='Review needed')
    until = '2099-01-01T00:00:00+00:00'
    assert memory.snooze_notification(notification.id, until=until).snoozed_until == until
    with closing(Memory.open(memory.store.path, namespace=memory.namespace)) as reopened:
        assert reopened.get_review_task(task.id).status == 'dismissed'
        assert reopened.get_notification(notification.id).status == 'snoozed'
    assert not memory.list_rollbacks(namespace=memory.namespace)


def test_clusters_abstractions_and_rejected_inference_never_become_active_claims(memory):
    a = memory.remember(memory_type='project', subject='project:fixture', predicate='current_milestone', object='M4', confidence=.92)
    b = memory.remember(memory_type='project', subject='M4', predicate='name', object='Reasoned Memory', confidence=.92)
    for subject in ['cluster-alpha', 'cluster-beta']:
        memory.remember(memory_type='fact', subject=subject, predicate='records', object='shared synthetic observation')
    before = {row.id for row in memory.list_claims(namespace=memory.namespace)}
    memory.run_inference(memory.namespace, engines=['logical', 'factual'], dry_run=False)
    pending = memory.list_inferences(memory.namespace)
    assert pending
    memory.reject_inference(pending[0].id, reason='Synthetic operator declined derived content')
    assert memory.read_inference(pending[0].id).status == 'rejected'
    abstraction = memory.create_abstraction(memory.namespace, source_ids=[a.id, b.id], source_type='claim',
        abstraction_text='Synthetic milestone description', abstraction_level=1, reason='Synthetic inspection')
    assert abstraction in memory.list_abstractions(namespace=memory.namespace)
    memory.build_semantic_clusters(memory.namespace)
    for cluster in memory.list_semantic_clusters(namespace=memory.namespace):
        assert memory.get_semantic_cluster(cluster.id) == cluster
    assert {row.id for row in memory.list_claims(namespace=memory.namespace)} == before
    assert not memory.list_abstractions(namespace='surface/other')
    with pytest.raises(NotFoundError):
        memory.get_semantic_cluster('cluster-missing')


def test_project_eval_and_decay_catalogs_respect_namespace(memory):
    project = memory.create_project(memory.namespace, 'synthetic-project', title='Synthetic project')
    evaluation = memory.create_eval_set(memory.namespace, name='Synthetic evaluation')
    assert project in memory.list_projects(namespace=memory.namespace)
    assert evaluation in memory.list_eval_sets(namespace=memory.namespace)
    assert not memory.list_projects(namespace='surface/other')
    assert not memory.list_eval_sets(namespace='surface/other')
    policy = memory.set_half_life_policy(namespace=memory.namespace, memory_type='fact', half_life_days=30, reason='Synthetic decay policy')
    assert policy in memory.list_half_life_policies(namespace=memory.namespace, memory_type='fact')
