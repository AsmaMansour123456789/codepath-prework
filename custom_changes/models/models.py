from odoo import fields, models, api, _
from odoo.tools import config
from odoo.exceptions import UserError
from psycopg2.extensions import TransactionRollbackError

import logging
import re

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def get_product_multiline_description_sale(self):
        name = self.display_name
        name = re.sub(r'\[[^\]]*\]', '', name).rstrip()
        if self.description_sale:
            name += '\n' + self.description_sale

        return name


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _cron_recurring_create_invoice(self):
        # return self._create_recurring_invoice(automatic=True)
        return self._create_recurring_invoice(automatic=False, is_cron=True)

    def _create_recurring_invoice(self, automatic=False, batch_size=30, is_cron=False):
        automatic = bool(automatic)
        auto_commit = automatic and not bool(config['test_enable'] or config['test_file'])
        Mail = self.env['mail.mail']
        today = fields.Date.today()
        invoiceable_categories = ['progress']

        if len(self) > 0:
            all_subscriptions = self.filtered(
                lambda so: so.is_subscription and so.subscription_management != 'upsell' and not so.payment_exception)
            need_cron_trigger = False
            invoiceable_categories.append('paused')
        else:
            search_domain = self._recurring_invoice_domain()
            all_subscriptions = self.search(search_domain, limit=batch_size + 1)
            need_cron_trigger = len(all_subscriptions) > batch_size
            if need_cron_trigger:
                all_subscriptions = all_subscriptions[:batch_size]

        if not all_subscriptions:
            return self.env['account.move']

        # don't spam sale with assigned emails.
        all_subscriptions = all_subscriptions.with_context(mail_auto_subscribe_no_notify=True)
        auto_close_subscription = all_subscriptions.filtered_domain([('end_date', '!=', False)])
        all_invoiceable_lines = all_subscriptions.with_context(recurring_automatic=automatic)._get_invoiceable_lines(
            final=False)
        auto_close_subscription._subscription_auto_close_and_renew()

        if automatic:
            all_subscriptions.write({'is_invoice_cron': True})

        lines_to_reset_qty = self.env['sale.order.line']
        account_moves = self.env['account.move']

        all_invoiceable_lines._reset_subscription_qty_to_invoice()
        if auto_commit:
            self.env.cr.commit()

        for subscription in all_subscriptions:
            if not (subscription.state == 'sale' and subscription.stage_category in invoiceable_categories):
                continue

            try:
                subscription = subscription[0]
                if subscription.payment_exception:
                    continue
                if auto_commit:
                    self.env.cr.commit()

                draft_invoices = subscription.invoice_ids.filtered(lambda am: am.state == 'draft')
                if not subscription.payment_token_id and draft_invoices:
                    if not is_cron:
                        raise UserError(_("There is already a draft invoice for subscription %s.", subscription.name))
                    continue

                if subscription.payment_token_id:
                    draft_invoices.button_cancel()

                invoiceable_lines = all_invoiceable_lines.filtered(lambda l: l.order_id.id == subscription.id)
                invoice_is_free, is_exception = subscription._invoice_is_considered_free(invoiceable_lines)

                if not invoiceable_lines or invoice_is_free:
                    if is_exception and automatic:
                        msg_body = _(
                            "Mix of negative recurring lines and non-recurring line. The contract should be fixed manually",
                            inv=self.next_invoice_date
                        )
                        subscription.message_post(body=msg_body)
                        subscription.payment_exception = True

                    elif not automatic or subscription.next_invoice_date <= today:
                        subscription._update_next_invoice_date()
                        if invoice_is_free:
                            for line in invoiceable_lines:
                                line.qty_invoiced = line.product_uom_qty
                            subscription._subscription_post_success_free_renewal()

                    if auto_commit:
                        self.env.cr.commit()
                    continue

                try:
                    invoice = subscription.with_context(recurring_automatic=automatic)._create_invoices()
                    lines_to_reset_qty |= invoiceable_lines
                except Exception as e:
                    if auto_commit:
                        self.env.cr.rollback()
                    elif isinstance(e, TransactionRollbackError) or not automatic:
                        raise

                    email_context = subscription._get_subscription_mail_payment_context()
                    error_message = _("Error during renewal of contract %s (Payment not recorded)", subscription.name)
                    _logger.exception(error_message)
                    mail = Mail.sudo().create({'body_html': error_message, 'subject': error_message,
                                               'email_to': email_context['responsible_email'], 'auto_delete': True})
                    mail.send()
                    continue

                if auto_commit:
                    self.env.cr.commit()

                if automatic:
                    existing_invoices = subscription._handle_automatic_invoices(auto_commit, invoice)
                    account_moves |= existing_invoices
                else:
                    account_moves |= invoice

                subscription.with_context(mail_notrack=True).write({'payment_exception': False})

            except Exception as error:
                _logger.exception("Error during renewal of contract %s",
                                  subscription.client_order_ref or subscription.name)
                if auto_commit:
                    self.env.cr.rollback()
                if not is_cron:
                    raise error

            else:
                if auto_commit:
                    self.env.cr.commit()

        lines_to_reset_qty._reset_subscription_quantity_post_invoice()
        all_subscriptions._process_invoices_to_send(account_moves, auto_commit)

        if not is_cron and automatic and not need_cron_trigger:
            cron_subs = self.search([('is_invoice_cron', '=', True)])
            cron_subs.write({'is_invoice_cron': False})

        if not need_cron_trigger:
            failing_subscriptions = self.search([('is_batch', '=', True)])
            failing_subscriptions.write({'is_batch': False})

        return account_moves


class StockMoveInherit(models.Model):
    _inherit = "stock.move"

    description_bl = fields.Text(compute="_compute_description_bl", string="Description BL")

    @api.depends('sale_line_id.name')
    def _compute_description_bl(self):
        for move in self:
            if move.sale_line_id:
                move.description_bl = move.sale_line_id.name
            else:
                move.description_bl = ''

# class StockMoveLineInherit(models.Model):
#     _inherit = "stock.move.line"
#
#     description_line_bl = fields.Text(related='product_id.description_pickingout', string="Description BL")





class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    project_id = fields.Many2one('project.project', string='Projet')
    task_id = fields.Many2one('project.task', string='Tâche', domain = "[('project_id','=', project_id)]" )
    # timesheet_ids = fields.One2many('account.analytic.line', 'helpdesk_ticket_id', 'Timesheets', ondelete='cascade')

    @api.model
    def create(self, values):
        record = super(HelpdeskTicket, self).create(values)
        record.sync_timesheets_to_task()
        return record

    def write(self, values):
        res = super(HelpdeskTicket, self).write(values)
        self.sync_timesheets_to_task()
        return res

    def sync_timesheets_to_task(self):
        if self.task_ticket_id:
            # Récupérer les anciennes entrées de timesheets liées à la tâche
            existing_timesheets = self.task_ticket_id.timesheet_ids
    
            # Mettre à jour les entrées existantes ou créer de nouvelles
            for timesheet in self.timesheet_ids:
                existing_timesheet = existing_timesheets.filtered(lambda t: t.date == timesheet.date and t.employee_id.id == timesheet.employee_id.id and t.name == timesheet.name)
                if existing_timesheet:
                    existing_timesheet.write({
                        'name': timesheet.name,
                        'unit_amount': timesheet.unit_amount,
                    })
                else:
                    self.task_ticket_id.timesheet_ids.create({
                        'date': timesheet.date,
                        'employee_id': timesheet.employee_id.id,
                        'name': timesheet.name,
                        'unit_amount': timesheet.unit_amount,
                        'task_id': self.task_ticket_id.id,
                    })
    

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.constrains('task_id', 'helpdesk_ticket_id')
    def _check_no_link_task_and_ticket(self):
        # En laissant le corps de la méthode vide, la contrainte est désactivée
        pass
