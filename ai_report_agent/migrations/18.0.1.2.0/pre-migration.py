import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add openai_model_preset and anthropic_model_preset columns if missing.

    Root cause: these Selection fields were added to ai.report.config after
    initial install but the module was never upgraded, so the DB columns were
    never created. This script adds them defensively before the ORM sync.
    """
    columns = {
        'openai_model_preset': 'VARCHAR',
        'anthropic_model_preset': 'VARCHAR',
    }
    for col, col_type in columns.items():
        cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ai_report_config' AND column_name = %s
            """,
            (col,),
        )
        if not cr.fetchone():
            cr.execute(
                f'ALTER TABLE ai_report_config ADD COLUMN {col} {col_type}'
            )
            _logger.info('ai_report_agent migration: added column ai_report_config.%s', col)
        else:
            _logger.info('ai_report_agent migration: column ai_report_config.%s already exists', col)
