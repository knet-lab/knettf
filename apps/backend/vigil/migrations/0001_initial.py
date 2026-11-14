"""
Initial migration: create vigil_detectionrecord as a PostgreSQL declarative-
partitioned table (RANGE by created_at, daily partitions).

- Pre-creates partitions for the past 89 days + today + tomorrow (91 total).
- Indexes are defined on the parent and inherited by all partitions.
"""

from django.db import migrations


CREATE_PARENT = """
CREATE TABLE IF NOT EXISTS vigil_detectionrecord (
    id            BIGSERIAL,
    src_ip        INET             NOT NULL,
    dst_ip        INET             NOT NULL,
    src_port      INTEGER          NOT NULL,
    dst_port      INTEGER          NOT NULL,
    protocol      VARCHAR(10)      NOT NULL,
    flow_input    JSONB            NOT NULL,
    model_name    VARCHAR(100)     NOT NULL,
    is_attack     BOOLEAN          NOT NULL,
    confidence    DOUBLE PRECISION NOT NULL,
    attack_type   VARCHAR(100),
    explanation   TEXT             NOT NULL DEFAULT '',
    raw_output    JSONB            NOT NULL DEFAULT '{}',
    cilium_action VARCHAR(50),
    cilium_reason TEXT             NOT NULL DEFAULT '',
    label         INTEGER,
    created_at    TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS vigil_dr_is_attack_idx  ON vigil_detectionrecord (is_attack);
CREATE INDEX IF NOT EXISTS vigil_dr_model_name_idx ON vigil_detectionrecord (model_name);
CREATE INDEX IF NOT EXISTS vigil_dr_created_at_idx ON vigil_detectionrecord (created_at DESC);
"""

CREATE_PARTITIONS = """
DO $$
DECLARE
    d DATE;
BEGIN
    FOR i IN -89..1 LOOP
        d := CURRENT_DATE + i;
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS vigil_detectionrecord_%s
             PARTITION OF vigil_detectionrecord
             FOR VALUES FROM (%L) TO (%L)',
            to_char(d, 'YYYY_MM_DD'),
            d::timestamptz,
            (d + 1)::timestamptz
        );
    END LOOP;
END;
$$;
"""


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS vigil_detectionrecord CASCADE;",
                CREATE_PARENT,
                CREATE_INDEXES,
                CREATE_PARTITIONS,
            ],
            reverse_sql="DROP TABLE IF EXISTS vigil_detectionrecord CASCADE;",
        ),
    ]
