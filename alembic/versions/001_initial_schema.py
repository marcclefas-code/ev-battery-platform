"""Initial schema - battery_entity, property_definition, scrape_plan v3 tables

Revision ID: 001_initial
Revises:
Create Date: 2026-05-18

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    entity_type_enum = postgresql.ENUM('pack', 'hv_module', 'hv_cell', 'aux_12v', 'aux_48v_mhev', name='entity_type', create_type=False)
    entity_type_enum.create(op.get_bind(), checkfirst=True)
    entity_status_enum = postgresql.ENUM('candidate', 'confirmed', 'deprecated', name='entity_status', create_type=False)
    entity_status_enum.create(op.get_bind(), checkfirst=True)
    pn_type_enum = postgresql.ENUM('service', 'superseded', 'etn', 'alias', 'oem_cross', 'aftermarket', name='pn_type', create_type=False)
    pn_type_enum.create(op.get_bind(), checkfirst=True)
    property_status_enum = postgresql.ENUM('candidate', 'confirmed', 'rejected', name='property_status', create_type=False)
    property_status_enum.create(op.get_bind(), checkfirst=True)
    relationship_type_enum = postgresql.ENUM('CONTAINS_MODULE', 'CONTAINS_CELL', 'USES_CONTROLLER', 'FITMENT_VEHICLE', 'SUPERSEDES', 'CROSS_REF_AFTERMARKET', 'CROSS_REF_OEM', name='relationship_type', create_type=False)
    relationship_type_enum.create(op.get_bind(), checkfirst=True)
    relationship_status_enum = postgresql.ENUM('candidate', 'confirmed', 'rejected', name='relationship_status', create_type=False)
    relationship_status_enum.create(op.get_bind(), checkfirst=True)
    task_severity_enum = postgresql.ENUM('low', 'medium', 'high', 'critical', name='task_severity', create_type=False)
    task_severity_enum.create(op.get_bind(), checkfirst=True)
    task_status_enum = postgresql.ENUM('open', 'in_review', 'resolved', 'dismissed', name='task_status', create_type=False)
    task_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table('battery_entity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_type', postgresql.ENUM('pack', 'hv_module', 'hv_cell', 'aux_12v', 'aux_48v_mhev', name='entity_type', create_type=False), nullable=False),
        sa.Column('canonical_name', sa.String(500), nullable=True),
        sa.Column('normalized_primary_part_number', sa.String(100), nullable=True, unique=True),
        sa.Column('occurrence_count', sa.Integer(), server_default='1'),
        sa.Column('status', postgresql.ENUM('candidate', 'confirmed', 'deprecated', name='entity_status', create_type=False), server_default='candidate'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_table('battery_part_number',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=False),
        sa.Column('raw', sa.String(200), nullable=False),
        sa.Column('normalized', sa.String(100), nullable=False),
        sa.Column('brand', sa.String(50), nullable=False),
        sa.Column('pn_type', postgresql.ENUM('service', 'superseded', 'etn', 'alias', 'oem_cross', 'aftermarket', name='pn_type', create_type=False), server_default='service'),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('evidence_quote', sa.String(1000), nullable=True),
        sa.Column('trust_weight', sa.Numeric(3, 2), server_default='0.50'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_part_number_normalized', 'battery_part_number', ['normalized'])
    op.create_index('idx_part_number_brand', 'battery_part_number', ['brand'])
    op.create_unique_constraint('uq_part_number_brand', 'battery_part_number', ['normalized', 'brand'])
    op.create_table('property_definition',
        sa.Column('code', sa.String(50), primary_key=True),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('data_type', sa.String(20), nullable=False),
        sa.Column('applies_to', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_table('property_statement',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=False),
        sa.Column('code', sa.String(50), sa.ForeignKey('property_definition.code'), nullable=False),
        sa.Column('value', postgresql.JSON(), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('evidence_quote', sa.String(2000), nullable=True),
        sa.Column('trust_weight', sa.Numeric(3, 2), server_default='0.50'),
        sa.Column('confidence', sa.Numeric(3, 2), server_default='0.50'),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('mayan_document_id', sa.String(100), nullable=True),
        sa.Column('status', postgresql.ENUM('candidate', 'confirmed', 'rejected', name='property_status', create_type=False), server_default='candidate'),
        sa.Column('alternative_values', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_property_entity_code', 'property_statement', ['entity_id', 'code'])
    op.create_table('battery_relationship',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('parent_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=False),
        sa.Column('child_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=True),
        sa.Column('relationship_type', postgresql.ENUM('CONTAINS_MODULE', 'CONTAINS_CELL', 'USES_CONTROLLER', 'FITMENT_VEHICLE', 'SUPERSEDES', 'CROSS_REF_AFTERMARKET', 'CROSS_REF_OEM', name='relationship_type', create_type=False), nullable=False),
        sa.Column('sequence_position', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), server_default='0.50'),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('evidence_quote', sa.String(2000), nullable=True),
        sa.Column('trust_weight', sa.Numeric(3, 2), server_default='0.50'),
        sa.Column('status', postgresql.ENUM('candidate', 'confirmed', 'rejected', name='relationship_status', create_type=False), server_default='candidate'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_table('vehicle_variant_code',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=False),
        sa.Column('make', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('variant_code', sa.String(50), nullable=True),
        sa.Column('year_from', sa.Integer(), nullable=True),
        sa.Column('year_to', sa.Integer(), nullable=True),
        sa.Column('engine_code', sa.String(50), nullable=True),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('trust_weight', sa.Numeric(3, 2), server_default='0.50'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_vehicle_make', 'vehicle_variant_code', ['make'])
    op.create_index('idx_vehicle_model', 'vehicle_variant_code', ['model'])
    op.create_table('discovered_spec',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('normalized_pn', sa.String(100), nullable=False),
        sa.Column('raw_context', sa.String(), nullable=True),
        sa.Column('occurrence_count', sa.Integer(), server_default='1'),
        sa.Column('first_seen', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('promoted_to_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('idx_discovered_pn', 'discovered_spec', ['normalized_pn'])
    op.create_table('scrape_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('source_kind', sa.String(50), nullable=False),
        sa.Column('extraction_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('trust_weight', sa.Numeric(3, 2), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('review_flags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('processing_ms', sa.Integer(), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=True),
        sa.Column('mayan_document_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_table('enrichment_review_task',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=False),
        sa.Column('flag_code', sa.String(100), nullable=False),
        sa.Column('severity', postgresql.ENUM('low', 'medium', 'high', 'critical', name='task_severity', create_type=False), server_default='medium'),
        sa.Column('description', sa.String(1000), nullable=False),
        sa.Column('status', postgresql.ENUM('open', 'in_review', 'resolved', 'dismissed', name='task_status', create_type=False), server_default='open'),
        sa.Column('assigned_to', sa.String(100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_table('scrape_plan',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('battery_entity.id'), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('source_kind', sa.String(50), nullable=False),
        sa.Column('brand', sa.String(50), nullable=True),
        sa.Column('wave_policy_key', sa.String(100), nullable=True),
        sa.Column('waves_planned', sa.Integer(), server_default='1'),
        sa.Column('waves_completed', sa.Integer(), server_default='0'),
        sa.Column('quorum_policy', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(50), server_default='open'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_table('scrape_attempt',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scrape_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scrape_plan.id'), nullable=False),
        sa.Column('wave_number', sa.Integer(), nullable=False),
        sa.Column('fetcher', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('source_kind', sa.String(50), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(50), server_default='scheduled'),
        sa.Column('blocked', sa.Boolean(), server_default='false'),
        sa.Column('block_reason', sa.String(500), nullable=True),
        sa.Column('raw_hash', sa.String(64), nullable=True),
        sa.Column('html_length', sa.Integer(), nullable=True),
        sa.Column('visible_text_length', sa.Integer(), nullable=True),
        sa.Column('extraction_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('evidence_quote_coverage', sa.Numeric(3, 2), nullable=True),
        sa.Column('payload_json', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_table('scrape_consensus_result',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scrape_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scrape_plan.id'), nullable=False),
        sa.Column('winning_attempt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scrape_attempt.id'), nullable=True),
        sa.Column('attempts_succeeded', sa.Integer(), server_default='0'),
        sa.Column('consensus_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('conflicting_fields', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('merged_payload_json', postgresql.JSON(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    mv_sql = (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS battery_cross_reference_search AS "
        "SELECT e.id AS entity_id, e.entity_type, e.canonical_name, e.status, e.normalized_primary_part_number, "
        "pn.brand, COALESCE(pn.trust_weight, 0.5) AS primary_pn_trust, "
        "(SELECT AVG(ps.confidence) FROM property_statement ps WHERE ps.entity_id = e.id AND ps.status = 'confirmed') AS avg_confidence, "
        "(SELECT COUNT(*) FROM property_statement ps WHERE ps.entity_id = e.id AND ps.status = 'confirmed') AS confirmed_props_count, "
        "e.occurrence_count, e.created_at, e.updated_at "
        "FROM battery_entity e "
        "LEFT JOIN battery_part_number pn ON pn.entity_id = e.id AND pn.pn_type = 'service'"
    )
    op.execute(mv_sql)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_battery_xref_entity ON battery_cross_reference_search(entity_id)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS battery_cross_reference_search")
    op.drop_table('scrape_consensus_result')
    op.drop_table('scrape_attempt')
    op.drop_table('scrape_plan')
    op.drop_table('enrichment_review_task')
    op.drop_table('scrape_log')
    op.drop_table('discovered_spec')
    op.drop_table('vehicle_variant_code')
    op.drop_table('battery_relationship')
    op.drop_table('property_statement')
    op.drop_table('property_definition')
    op.drop_table('battery_part_number')
    op.drop_table('battery_entity')
