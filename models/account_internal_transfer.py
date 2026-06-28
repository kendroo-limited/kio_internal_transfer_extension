from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountInternalTransfer(models.Model):
    _name = 'account.internal.transfer'
    _description = 'Internal Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name desc'

    name = fields.Char(
        string="Number",
        required=True,
        copy=False,
        readonly=True,
        tracking=True,
        default=lambda self: _('New'),
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True,
        invisible=True,
    )

    payment_method = fields.Selection([
        ('bkash', 'Bkash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('upay', 'Upay'),
    ], string="Legacy Payment Method", tracking=True)

    payment_journal_id = fields.Many2one(
        'account.journal',
        string="Payment Method",
        domain="[('type', 'in', ['bank', 'cash'])]",
        tracking=True,
    )

    journal_id = fields.Many2one(
        'account.journal',
        string="Bank Journal",
        domain="[('type', 'in', ['bank', 'cash'])]",
        required=True,
        tracking=True,
    )

    date = fields.Date(
        string="Date",
        required=True,
        tracking=True,
        default=fields.Date.context_today,
    )

    transaction = fields.Char(
        string="Transaction ID",
        tracking=True,
        required=True,
    )

    amount = fields.Float(string="Amount", required=True, tracking=True)

    settlement_charge_percent = fields.Float(
        string="Settlement Charge (%)",
        tracking=True,
    )

    settlement_charge = fields.Float(
        string="Settlement Charge",
        compute="_compute_amounts",
        store=True,
        tracking=True,
    )

    net_amount = fields.Float(
        string="Net Amount",
        compute="_compute_amounts",
        store=True,
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('transferred', 'Transferred'),
    ], default='draft', tracking=True)

    move_id = fields.Many2one(
        'account.move',
        string="Journal Entry",
        readonly=True,
        copy=False,
        tracking=True,
    )

    history_count = fields.Integer(
        string="History Count",
        compute="_compute_history_count",
        tracking=True,
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('account.internal.transfer') or _('New')
        return super().create(vals)

    @api.depends('amount', 'settlement_charge_percent')
    def _compute_amounts(self):
        for rec in self:
            rec.settlement_charge = rec.amount * rec.settlement_charge_percent / 100
            rec.net_amount = rec.amount - rec.settlement_charge

    @api.depends('move_id')
    def _compute_history_count(self):
        for rec in self:
            rec.history_count = 1 if rec.move_id else 0

    def action_view_history(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No history record is available for this transfer yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('History'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
            'target': 'current',
        }

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != 'transferred':
                continue
            if rec.move_id:
                rec.move_id.button_draft()
                rec.move_id.unlink()
            rec.write({
                'move_id': False,
                'state': 'draft',
            })

    def _get_misc_journal(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.journal_id.company_id.id),
            ('type', '=', 'general'),
        ], limit=1)
        if not journal:
            raise UserError(_("No miscellaneous journal was found for company %s.") % self.journal_id.company_id.display_name)
        return journal

    def _get_payment_method_account(self):
        self.ensure_one()
        payment_account = self.payment_journal_id.default_account_id
        if not payment_account:
            raise UserError(
                _("The selected payment journal '%s' must have a default account.")
                % self.payment_journal_id.display_name
            )
        return payment_account

    def _get_settlement_account(self):
        self.ensure_one()
        payment_method_name = self.payment_journal_id.name
        account_model = self.env['account.account']
        account = account_model.search([
            ('company_id', '=', self.journal_id.company_id.id),
            ('name', '=ilike', '%s Charge Expense' % payment_method_name),
        ], limit=1)
        if not account:
            account = account_model.search([
                ('company_id', '=', self.journal_id.company_id.id),
                ('name', '=ilike', 'Settlement Charge Expense'),
            ], limit=1)
        if not account:
            account = account_model.search([
                ('company_id', '=', self.journal_id.company_id.id),
                ('name', '=ilike', 'Settlement Charge'),
            ], limit=1)
        if not account:
            account = account_model.search([
                ('company_id', '=', self.journal_id.company_id.id),
                ('name', 'ilike', 'Settlement Charge'),
            ], limit=1)
        if not account:
            account = account_model.search([
                ('company_id', '=', self.journal_id.company_id.id),
                ('code', '=', '500310'),
            ], limit=1)
        if not account:
            raise UserError(_("No settlement charge expense account was found for company %s.") % self.journal_id.company_id.display_name)
        return account

    def action_transfer(self):
        for rec in self:
            if rec.state == 'transferred':
                raise UserError(_("This internal transfer has already been posted."))
            if not rec.payment_journal_id:
                raise UserError(_("Please select a payment journal."))
            if not rec.payment_journal_id.default_account_id:
                raise UserError(_("The selected payment journal must have a default account."))
            if not rec.journal_id.default_account_id:
                raise UserError(_("The selected bank journal must have a default account."))

            payment_method_name = rec.payment_journal_id.name
            payment_account = rec._get_payment_method_account()
            settlement_account = rec._get_settlement_account() if rec.settlement_charge else False
            move_journal = rec._get_misc_journal()

            line_vals = [
                (0, 0, {
                    'name': _('Bank Debit'),
                    'account_id': rec.journal_id.default_account_id.id,
                    'debit': rec.net_amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': _('%s Credit') % payment_method_name,
                    'account_id': payment_account.id,
                    'debit': 0.0,
                    'credit': rec.amount,
                }),
            ]

            if settlement_account and rec.settlement_charge:
                line_vals.insert(1, (0, 0, {
                    'name': _('Settlement Debit'),
                    'account_id': settlement_account.id,
                    'debit': rec.settlement_charge,
                    'credit': 0.0,
                }))

            move = self.env['account.move'].create({
                'move_type': 'entry',
                'date': rec.date,
                'ref': _('%s To %s') % (payment_method_name.upper(), rec.journal_id.name.upper()),
                'journal_id': move_journal.id,
                'line_ids': line_vals,
            })
            move.action_post()
            rec.move_id = move.id
            rec.state = 'transferred'
