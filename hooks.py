def _column_type(cr, table_name, column_name):
    cr.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    result = cr.fetchone()
    return result[0] if result else None


def pre_init_hook(cr):
    table_name = 'account_internal_transfer'
    column_name = 'payment_method'
    legacy_column = 'payment_method_legacy'

    column_type = _column_type(cr, table_name, column_name)
    if column_type and column_type != 'integer':
        if not _column_type(cr, table_name, legacy_column):
            cr.execute(
                f'ALTER TABLE "{table_name}" RENAME COLUMN "{column_name}" TO "{legacy_column}"'
            )
        cr.execute(
            f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{column_name}" integer'
        )

    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
         WHERE field_id IN (
            SELECT id
              FROM ir_model_fields
             WHERE model = %s
               AND name = %s
         )
        """,
        ('account.internal.transfer', 'payment_method'),
    )

    if not _column_type(cr, table_name, legacy_column):
        return

    cr.execute(
        f"""
        UPDATE {table_name} AS transfer
           SET payment_method = source_journal.id
          FROM account_journal AS target_journal
          JOIN LATERAL (
                SELECT journal.id
                  FROM account_journal AS journal
                 WHERE journal.type = 'bank'
                   AND journal.company_id = target_journal.company_id
                   AND (
                        lower(journal.name) = lower(transfer.{legacy_column})
                     OR lower(coalesce(journal.code, '')) = lower(transfer.{legacy_column})
                   )
                 ORDER BY journal.id
                 LIMIT 1
          ) AS source_journal ON TRUE
         WHERE transfer.journal_id = target_journal.id
           AND transfer.payment_method IS NULL
        """
    )

    cr.execute(
        f"""
        UPDATE {table_name}
           SET payment_method = journal_id
         WHERE payment_method IS NULL
           AND journal_id IS NOT NULL
        """
    )
